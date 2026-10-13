import copy

import pytest
from pydantic import ValidationError

from app.core.llm import LLMBadJSON
from app.demos.contracts.review import check_evidence, normalize, sort_review
from app.demos.contracts.schema import ContractReview, Evidence
from tests.conftest import make_pdf, new_session, upload
from tests.test_api import error_of

PAGES = [
    "Mutual non-disclosure agreement between Alder Robotics Ltd and Birch Analytics GmbH.",
    "Term. This agreement lasts two years from the Effective Date.\n"
    "Confidential Information must not be shared with any third party.",
    "Governing law. This agreement is governed by the laws of England and Wales.",
]


def evidence(page: int, quote: str) -> Evidence:
    return Evidence(page=page, quote=quote)


def checked(page: int, quote: str, pages=PAGES) -> Evidence:
    return check_evidence(evidence(page, quote), [normalize(p) for p in pages])


def test_quote_on_the_cited_page_is_verified():
    result = checked(2, "This agreement lasts two years from the Effective Date.")
    assert (result.page, result.verified) == (2, True)


def test_quote_found_only_on_another_page_moves_to_that_page():
    result = checked(1, "governed by the laws of England and Wales")
    assert (result.page, result.verified) == (3, True)


@pytest.mark.parametrize(
    "page, quote",
    [
        (2, "This agreement lasts three years from the Effective Date."),
        (9, "governed by the laws of Scotland"),
        (1, "  "),
    ],
)
def test_quote_missing_from_the_document_is_unverified(page, quote):
    result = checked(page, quote)
    assert result.verified is False
    assert result.page == page


@pytest.mark.parametrize("cited, expected", [(1, 2), (5, 4), (3, 2)])
def test_quote_on_several_other_pages_moves_to_the_nearest(cited, expected):
    pages = ["Cover page.", "Payment is due in 30 days.", "Signatures.", "Payment is due in 30 days.", "Annex."]
    result = checked(cited, "Payment is due in 30 days.", pages)
    assert (result.page, result.verified) == (expected, True)


@pytest.mark.parametrize(
    "quote",
    [
        "TERM. this agreement   lasts two\nyears",
        "“Confidential Information must not be shared”",
        "lasts two years from the Effective Date. Confidential Information",
    ],
)
def test_whitespace_case_and_curly_quotes_still_match(quote):
    assert checked(2, quote).verified is True


def test_curly_apostrophe_in_the_document_matches_a_straight_one():
    pages = ["The Tenant’s deposit is returned within 14 days."]
    assert checked(1, "the tenant's deposit is returned", pages).verified is True


def review_json(**overrides) -> dict:
    ev = {"page": 1, "quote": "Mutual non-disclosure agreement"}
    data = {
        "summary": "A mutual NDA.",
        "contract_type": "Mutual NDA",
        "parties": [{"name": "Alder Robotics Ltd", "role": "Party"}],
        "key_terms": [{"label": "Term", "value": "Two years", "evidence": ev}],
        "clauses": [{"kind": "confidentiality", "title": "Secrecy", "plain_english": "Keep it secret.", "evidence": ev}],
        "risks": [{"severity": "low", "title": "Broad", "explanation": "Covers a lot.", "evidence": ev}],
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    "path, value",
    [(("clauses", 0, "kind"), "warranty"), (("risks", 0, "severity"), "critical")],
)
def test_schema_rejects_unknown_kind_and_severity(path, value):
    data = review_json()
    data[path[0]][path[1]][path[2]] = value
    with pytest.raises(ValidationError) as exc:
        ContractReview.model_validate(data)
    assert exc.value.errors()[0]["loc"] == path


def test_risks_sort_by_severity_then_page_and_clauses_by_kind():
    def risk(severity, page):
        return {"severity": severity, "title": f"{severity}{page}", "explanation": ".", "evidence": {"page": page, "quote": "q"}}

    def clause(kind, page):
        return {"kind": kind, "title": f"{kind}{page}", "plain_english": ".", "evidence": {"page": page, "quote": "q"}}

    review = ContractReview.model_validate(
        review_json(
            risks=[risk("low", 1), risk("high", 5), risk("medium", 2), risk("high", 3)],
            clauses=[clause("other", 1), clause("governing_law", 4), clause("termination", 6), clause("termination", 2)],
        )
    )
    result = sort_review(review)
    assert [r.title for r in result.risks] == ["high3", "high5", "medium2", "low1"]
    assert [c.title for c in result.clauses] == ["termination2", "termination6", "governing_law4", "other1"]


def review_pdf(client, data: bytes, name: str = "nda.pdf", headers=None, content_type="application/pdf"):
    return client.post("/api/contracts/review", files={"file": (name, data, content_type)}, headers=headers)


class ScriptedJSON:
    """Stands in for complete_json: returns or raises each scripted reply in turn."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts: list[str] = []

    async def __call__(self, system: str, user: str) -> dict:
        self.prompts.append(user)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return copy.deepcopy(reply)


def test_review_happy_path_with_the_fake_model(client):
    response = review_pdf(client, make_pdf(PAGES))
    assert response.status_code == 200
    body = response.json()
    assert body["document_name"] == "nda.pdf"
    assert body["pages"] == 3
    review = body["review"]
    assert set(review) == {"summary", "contract_type", "parties", "key_terms", "clauses", "risks"}
    for item in review["key_terms"] + review["clauses"] + review["risks"]:
        assert item["evidence"]["page"] == 1
        assert item["evidence"]["verified"] is True
        assert item["evidence"]["quote"].startswith("Mutual non-disclosure agreement")


def test_review_checks_model_quotes_against_the_pdf(client):
    reply = review_json(
        key_terms=[
            {"label": "Term", "value": "Two years", "evidence": {"page": 3, "quote": "this AGREEMENT lasts two years"}},
            {"label": "Fee", "value": "None", "evidence": {"page": 2, "quote": "No fee is payable", "verified": True}},
        ]
    )
    client.app.state.llm.complete_json = ScriptedJSON(reply)
    response = review_pdf(client, make_pdf(PAGES))
    assert response.status_code == 200
    terms = response.json()["review"]["key_terms"]
    assert terms[0]["evidence"] == {"page": 2, "quote": "this AGREEMENT lasts two years", "verified": True}
    assert terms[1]["evidence"]["verified"] is False


@pytest.mark.parametrize(
    "first, problem",
    [
        (LLMBadJSON("The reply was not valid JSON (Expecting value)."), "not valid JSON"),
        (review_json(risks=[{"severity": "critical", "title": "x", "explanation": "y", "evidence": {"page": 1, "quote": "q"}}]), "risks.0.severity"),
    ],
)
def test_bad_reply_is_retried_once_with_the_reason(client, first, problem):
    scripted = ScriptedJSON(first, review_json())
    client.app.state.llm.complete_json = scripted
    response = review_pdf(client, make_pdf(PAGES))
    assert response.status_code == 200
    assert len(scripted.prompts) == 2
    assert problem not in scripted.prompts[0]
    assert problem in scripted.prompts[1]
    assert scripted.prompts[1].startswith(scripted.prompts[0])


def test_two_bad_replies_are_llm_error(client):
    scripted = ScriptedJSON(LLMBadJSON("not JSON"), review_json(clauses="none"))
    client.app.state.llm.complete_json = scripted
    response = review_pdf(client, make_pdf(PAGES))
    assert error_of(response) == (502, "llm_error")
    assert len(scripted.prompts) == 2


def test_prompt_marks_every_page(client):
    scripted = ScriptedJSON(review_json())
    client.app.state.llm.complete_json = scripted
    review_pdf(client, make_pdf(PAGES))
    prompt = scripted.prompts[0]
    assert prompt.index("=== Page 1 ===") < prompt.index("Alder Robotics") < prompt.index("=== Page 2 ===")
    assert prompt.index("=== Page 3 ===") < prompt.index("England and Wales")


def test_too_many_pages_names_the_contract_limit(make_client):
    client = make_client(contract_max_pages=2)
    response = review_pdf(client, make_pdf(PAGES))
    assert error_of(response) == (413, "file_too_large")
    assert "2 pages" in response.json()["error"]["message"]


def test_non_pdf_is_rejected(client):
    response = review_pdf(client, b"just some text", name="notes.txt", content_type="text/plain")
    assert error_of(response) == (400, "not_a_pdf")


def test_missing_file_is_rejected(client):
    assert error_of(client.post("/api/contracts/review")) == (400, "not_a_pdf")


def test_rate_limit_is_shared_with_chat(make_client):
    client = make_client(rate_limit_per_minute=2)
    ip = {"X-Forwarded-For": "203.0.113.9"}
    session_id = new_session(client)
    assert upload(client, session_id, make_pdf(["text"]), headers=ip).status_code == 201
    assert review_pdf(client, make_pdf(PAGES), headers=ip).status_code == 200
    assert error_of(review_pdf(client, make_pdf(PAGES), headers=ip)) == (429, "rate_limited")
    assert error_of(upload(client, session_id, make_pdf(["text"]), headers=ip)) == (429, "rate_limited")

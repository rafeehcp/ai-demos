from app.core.llm import LLMQuotaError
from tests.conftest import make_pdf, new_session, upload

LEASE_PAGES = [
    "Residential lease agreement between the landlord and the tenant. "
    "The monthly rent is due on the first day of each month by bank transfer.",
    "Pets. The tenant may keep one cat or one small dog with written consent. "
    "Parking. One parking space in the rear lot is assigned to the unit.",
    "Early termination. After the first year, the tenant may terminate this lease "
    "by giving sixty days written notice to the landlord.",
]


def error_of(response) -> tuple[int, str]:
    body = response.json()
    assert set(body) == {"error"} and set(body["error"]) == {"code", "message"}
    assert body["error"]["message"]
    return response.status_code, body["error"]["code"]


def test_health_and_config(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/config").json() == {
        "max_documents": 3,
        "max_file_mb": 10,
        "max_pages": 100,
        "contract_max_pages": 40,
        "invoice_max_files": 5,
        "invoice_max_pages": 5,
        "provider_label": "Offline fake model",
    }


def test_end_to_end_answer_cites_the_page_with_the_fact(client):
    session_id = new_session(client)

    response = upload(client, session_id, make_pdf(LEASE_PAGES), name="lease.pdf")
    assert response.status_code == 201
    document = response.json()
    assert document["name"] == "lease.pdf"
    assert document["pages"] == 3
    assert document["chunks"] == 3
    assert document["id"].startswith("d_")

    listed = client.get(f"/api/sessions/{session_id}/documents")
    assert listed.status_code == 200
    assert listed.json() == {"documents": [document]}

    response = client.post(
        f"/api/sessions/{session_id}/ask",
        json={"question": "How much written notice does the tenant need to terminate early?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "[1]" in body["answer"]
    assert len(body["citations"]) == 1
    citation = body["citations"][0]
    assert citation["n"] == 1
    assert citation["document_id"] == document["id"]
    assert citation["document_name"] == "lease.pdf"
    assert citation["page"] == 3
    assert "sixty days written notice" in citation["quote"]

    response = client.post(
        f"/api/sessions/{session_id}/ask", json={"question": "Which parking space is assigned?"}
    )
    assert response.json()["citations"][0]["page"] == 2

    assert client.delete(f"/api/sessions/{session_id}/documents/{document['id']}").status_code == 204
    assert client.get(f"/api/sessions/{session_id}/documents").json() == {"documents": []}
    response = client.post(f"/api/sessions/{session_id}/ask", json={"question": "Anything?"})
    assert error_of(response) == (409, "no_documents")


def test_non_pdf_is_rejected(client):
    session_id = new_session(client)
    response = upload(client, session_id, b"hello, I am a text file", name="notes.txt", content_type="text/plain")
    assert error_of(response) == (400, "not_a_pdf")


def test_corrupt_pdf_is_rejected(client):
    session_id = new_session(client)
    response = upload(client, session_id, b"%PDF-1.7\n garbage garbage")
    assert error_of(response) == (400, "not_a_pdf")


def test_missing_file_field_is_rejected(client):
    session_id = new_session(client)
    response = client.post(f"/api/sessions/{session_id}/documents", data={"other": "x"})
    assert error_of(response) == (400, "not_a_pdf")


def test_blank_pdf_has_no_text(client):
    session_id = new_session(client)
    response = upload(client, session_id, make_pdf([None, None]))
    assert error_of(response) == (400, "no_text")
    assert client.get(f"/api/sessions/{session_id}/documents").json() == {"documents": []}


def test_oversize_file_is_rejected(make_client):
    client = make_client(max_file_mb=1)
    session_id = new_session(client)
    data = make_pdf(["fine"]) + b" " * (1024 * 1024)
    response = upload(client, session_id, data)
    assert error_of(response) == (413, "file_too_large")


def test_too_many_pages_is_rejected(make_client):
    client = make_client(max_pages=2)
    session_id = new_session(client)
    response = upload(client, session_id, make_pdf(["a", "b", "c"]))
    assert error_of(response) == (413, "file_too_large")


def test_fourth_document_is_rejected(client):
    session_id = new_session(client)
    for i in range(3):
        assert upload(client, session_id, make_pdf([f"document {i}"]), name=f"{i}.pdf").status_code == 201
    response = upload(client, session_id, make_pdf(["one too many"]))
    assert error_of(response) == (409, "too_many_documents")
    names = [d["name"] for d in client.get(f"/api/sessions/{session_id}/documents").json()["documents"]]
    assert names == ["0.pdf", "1.pdf", "2.pdf"]


def test_unknown_session_is_404(client):
    for response in (
        client.get("/api/sessions/s_nope/documents"),
        upload(client, "s_nope", make_pdf(["x"])),
        client.post("/api/sessions/s_nope/ask", json={"question": "hi"}),
        client.delete("/api/sessions/s_nope/documents/d_1"),
    ):
        assert error_of(response) == (404, "session_not_found")


def test_blank_or_long_question_is_rejected(client):
    session_id = new_session(client)
    upload(client, session_id, make_pdf(["text"]))
    for payload in ({"question": "   "}, {"question": "x" * 1001}, {}):
        response = client.post(f"/api/sessions/{session_id}/ask", json=payload)
        assert error_of(response) == (400, "empty_question")


def test_malformed_body_uses_error_shape(client):
    session_id = new_session(client)
    response = client.post(f"/api/sessions/{session_id}/ask", content=b"not json", headers={"content-type": "application/json"})
    assert error_of(response) == (400, "invalid_request")


def test_rate_limit_counts_uploads_and_asks_per_ip(make_client):
    client = make_client(rate_limit_per_minute=3)
    session_id = new_session(client)
    def forwarded(spoofed: str) -> dict[str, str]:
        return {"X-Forwarded-For": f"{spoofed}, 203.0.113.7"}

    assert upload(client, session_id, make_pdf(["text"]), headers=forwarded("1.1.1.1")).status_code == 201
    for spoofed in ("2.2.2.2", "3.3.3.3"):
        response = client.post(f"/api/sessions/{session_id}/ask", json={"question": "text?"}, headers=forwarded(spoofed))
        assert response.status_code == 200
    response = client.post(f"/api/sessions/{session_id}/ask", json={"question": "text?"}, headers=forwarded("4.4.4.4"))
    assert error_of(response) == (429, "rate_limited")
    assert 1 <= int(response.headers["Retry-After"]) <= 60

    other_ip = {"X-Forwarded-For": "198.51.100.1"}
    response = client.post(f"/api/sessions/{session_id}/ask", json={"question": "text?"}, headers=other_ip)
    assert response.status_code == 200


def test_llm_quota_maps_to_503(client):
    session_id = new_session(client)
    upload(client, session_id, make_pdf(["text"]))

    async def out_of_quota(system: str, user: str) -> str:
        raise LLMQuotaError()

    client.app.state.llm.complete = out_of_quota
    response = client.post(f"/api/sessions/{session_id}/ask", json={"question": "text?"})
    assert error_of(response) == (503, "llm_quota")


def test_unexpected_error_hides_details(client):
    session_id = new_session(client)
    upload(client, session_id, make_pdf(["text"]))

    async def broken(system: str, user: str) -> str:
        raise RuntimeError("secret internal detail")

    client.app.state.llm.complete = broken
    response = client.post(f"/api/sessions/{session_id}/ask", json={"question": "text?"})
    assert error_of(response) == (500, "internal_error")
    assert "secret" not in response.text


def test_cors_allows_configured_origin(make_client):
    client = make_client(cors_origins="https://demo.example, http://localhost:3000")
    response = client.get("/api/health", headers={"Origin": "https://demo.example"})
    assert response.headers["access-control-allow-origin"] == "https://demo.example"
    response = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers

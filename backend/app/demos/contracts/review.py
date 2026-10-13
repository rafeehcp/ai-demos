import json
import logging
import unicodedata
from typing import Sequence

from pydantic import ValidationError

from app.core.llm import LLMBadJSON, LLMError, LLMProvider
from app.demos.contracts.schema import ClauseKind, ContractReview, Evidence

logger = logging.getLogger(__name__)

_EXAMPLE = {
    "summary": "2 to 4 plain sentences: what the contract is, who it binds, and what matters most.",
    "contract_type": "Short name such as Residential lease or Mutual NDA",
    "parties": [{"name": "Name as written in the contract", "role": "Landlord, Client, Disclosing party, ..."}],
    "key_terms": [
        {
            "label": "Monthly rent",
            "value": "1,450 USD, due on the 1st",
            "evidence": {"page": 1, "quote": "exact text copied from that page"},
        }
    ],
    "clauses": [
        {
            "kind": "termination",
            "title": "Early termination",
            "plain_english": "What the clause means for the reader, in one or two sentences.",
            "evidence": {"page": 3, "quote": "exact text copied from that page"},
        }
    ],
    "risks": [
        {
            "severity": "medium",
            "title": "Termination fee",
            "explanation": "Who the risk falls on and why it matters, in one or two sentences.",
            "evidence": {"page": 3, "quote": "exact text copied from that page"},
        }
    ],
}

SYSTEM_PROMPT = f"""You review contracts for a reader who is not a lawyer.
The contract text follows, with a line "=== Page N ===" before each page.
Reply with one JSON object and nothing else, shaped like this example:

{json.dumps(_EXAMPLE, indent=2)}

Rules:
- Every quote is copied character for character from a single page of the contract, 10 to 300 characters long. Do not paraphrase, shorten, add ellipses, or join text from different places. "page" is the N of the "=== Page N ===" line above the quoted text.
- clauses: one entry for each of these kinds the contract covers: {", ".join(k.value for k in ClauseKind if k is not ClauseKind.other)}. Add "other" entries for any further clause a signer should know about.
- risks: every term a careful lawyer would flag for either party, typically 4 to 10: terms that are one-sided, unusual, open-ended, or could cost a party money, rights or flexibility. Check payment, termination, renewal, liability, indemnity, intellectual property and restrictions on future work. "severity" is "high", "medium" or "low". Say which party bears the risk.
- key_terms: every date, duration, amount of money, fee, notice period and renewal term, with the value as the contract states it.
- Use only the contract. Leave out anything it doesn't say.
- Every text value is plain prose: no Markdown, asterisks, bullet points or headings. Titles and labels are short and in sentence case."""

_RETRY_NOTE = "\n\nYour previous reply was rejected: {problem}\nReply again with one JSON object that follows the rules."
_MAX_ERRORS_IN_RETRY = 8


def build_user_prompt(pages: Sequence[str]) -> str:
    return "\n\n".join(f"=== Page {n} ===\n{text.strip()}" for n, text in enumerate(pages, start=1))


async def review_contract(llm: LLMProvider, pages: Sequence[str]) -> ContractReview:
    """Ask the model for a review, retry once on a malformed reply, then check every quote."""
    user = build_user_prompt(pages)
    prompt = user
    for attempt in (1, 2):
        try:
            review = ContractReview.model_validate(await llm.complete_json(SYSTEM_PROMPT, prompt))
        except LLMBadJSON as exc:
            problem = exc.detail
        except ValidationError as exc:
            problem = describe_validation_error(exc)
        else:
            return sort_review(verify_evidence(review, pages))
        logger.warning("contract review attempt %d rejected: %s", attempt, problem)
        prompt = user + _RETRY_NOTE.format(problem=problem)
    raise LLMError("The AI model returned a review the app couldn't read. Please try again.")


def describe_validation_error(exc: ValidationError) -> str:
    errors = exc.errors(include_url=False)
    parts = [
        f"{'.'.join(str(p) for p in e['loc']) or 'reply'}: {e['msg']}" for e in errors[:_MAX_ERRORS_IN_RETRY]
    ]
    if len(errors) > _MAX_ERRORS_IN_RETRY:
        parts.append(f"and {len(errors) - _MAX_ERRORS_IN_RETRY} more")
    return "; ".join(parts)


_QUOTE_CHARS = str.maketrans(
    {
        "‘": "'",
        "’": "'",
        "‚": "'",
        "‛": "'",
        "′": "'",
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "″": '"',
    }
)


def normalize(text: str) -> str:
    """Fold differences between PDF text and a model's copy of it that don't change the words."""
    folded = unicodedata.normalize("NFKC", text).translate(_QUOTE_CHARS).lower()
    return " ".join(folded.split())


def check_evidence(evidence: Evidence, normalized_pages: Sequence[str]) -> Evidence:
    # Models sometimes wrap a quote in quotation marks. Trimming only shortens
    # the quote, so it can't turn a mismatch into a false match.
    quote = normalize(evidence.quote).strip("'\" ")
    cited = evidence.page - 1
    if quote and 0 <= cited < len(normalized_pages) and quote in normalized_pages[cited]:
        return evidence.model_copy(update={"verified": True})
    elsewhere = [i for i, page in enumerate(normalized_pages) if i != cited and quote and quote in page]
    if len(elsewhere) == 1:
        return evidence.model_copy(update={"page": elsewhere[0] + 1, "verified": True})
    return evidence.model_copy(update={"verified": False})


def verify_evidence(review: ContractReview, pages: Sequence[str]) -> ContractReview:
    normalized = [normalize(p) for p in pages]

    def checked(item):
        return item.model_copy(update={"evidence": check_evidence(item.evidence, normalized)})

    return review.model_copy(
        update={
            "key_terms": [checked(t) for t in review.key_terms],
            "clauses": [checked(c) for c in review.clauses],
            "risks": [checked(r) for r in review.risks],
        }
    )


_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
_KIND_RANK = {kind: rank for rank, kind in enumerate(ClauseKind)}


def sort_review(review: ContractReview) -> ContractReview:
    return review.model_copy(
        update={
            "risks": sorted(review.risks, key=lambda r: (_SEVERITY_RANK[r.severity], r.evidence.page)),
            "clauses": sorted(review.clauses, key=lambda c: (_KIND_RANK[c.kind], c.evidence.page)),
        }
    )

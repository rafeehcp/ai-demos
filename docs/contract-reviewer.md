# Demo 2: Contract reviewer

A visitor uploads one contract PDF and gets a structured review: who the parties are, the key dates and money terms, the clauses that matter, and the risks, each backed by a quote and a page number. The selling point is that **every quote is checked against the document**. A quote the model can't back up is never shown as fact.

## Scope

- One contract per review, up to `CONTRACT_MAX_PAGES` (default 40). No RAG: the whole contract fits in one Gemini context, and the reviewer has to read all of it anyway.
- Single shot. No follow-up chat, which demo 1 already shows.
- Not legal advice. The UI says so next to the results.

## Data shape

```text
ContractReview
├─ summary: str                      2–4 plain sentences
├─ contract_type: str                "Residential lease", "Mutual NDA", ...
├─ parties: list[Party]              Party = (name, role)
├─ key_terms: list[KeyTerm]          dates, money, notice periods, renewal
│    KeyTerm = (label, value, evidence: Evidence)
├─ clauses: list[Clause]
│    Clause = (kind: ClauseKind, title, plain_english, evidence: Evidence)
└─ risks: list[Risk]                 most severe first
     Risk = (severity: "high"|"medium"|"low", title, explanation, evidence: Evidence)

Evidence = (page: int, quote: str, verified: bool)

ClauseKind = termination | renewal | payment | liability | indemnity | confidentiality
           | intellectual_property | governing_law | dispute_resolution | non_compete | other
```

`ClauseKind` is a closed enum so the frontend can give each kind a fixed label and order.

## Pipeline

1. **Extract.** `core/pdf.extract_pages` (reused from demo 1), with the lower page limit.
2. **Prompt.** Send the full text with explicit page markers (`=== Page 3 ===`) and ask for JSON matching the schema above, minus `verified`. Use `response_format: {"type": "json_object"}` and plain-prose strings with no Markdown. Quotes must be copied exactly from the contract, 10–300 characters.
3. **Parse.** Validate with pydantic at the boundary. On invalid JSON or schema, retry once with the validation error appended. If it fails again, return `502 llm_error`.
4. **Verify evidence.** For each `Evidence`, normalize whitespace, case and quote characters, then look for the quote on the cited page. If it isn't there, look on every other page and move `page` to the nearest page where it's found. `verified` is true only on an exact normalized match. Items with an unverified quote are still returned, but the UI marks them as unverified and never shows their quote as a citation.
5. **Sort.** Risks by severity, then by page. Clauses in `ClauseKind` order.

The provider needs a JSON-mode completion. Add `complete_json(system, user) -> dict` to `LLMProvider` (OpenAI-compatible: same fallback chain as `complete`, with `response_format`). `FakeProvider.complete_json` returns a fixed, valid review built from the first page's text, so tests and offline runs work.

## API

Same error shape and codes as [api.md](api.md). Reuses the session store, rate limiter and PDF checks.

### POST /api/contracts/review

Multipart field `file`. No session: the review is computed and returned in one call, and nothing is kept on the server.

`200`:

```json
{
  "document_name": "lease.pdf",
  "pages": 12,
  "review": {
    "summary": "A one-year residential lease ...",
    "contract_type": "Residential lease",
    "parties": [{ "name": "Harbor Homes LLC", "role": "Landlord" }],
    "key_terms": [
      { "label": "Monthly rent", "value": "1,450 USD, due on the 1st",
        "evidence": { "page": 1, "quote": "Monthly rent is 1,450 USD", "verified": true } }
    ],
    "clauses": [
      { "kind": "termination", "title": "Early termination",
        "plain_english": "After the first year, the tenant can leave with 60 days' notice and a fee of one month's rent.",
        "evidence": { "page": 3, "quote": "...", "verified": true } }
    ],
    "risks": [
      { "severity": "medium", "title": "Termination fee",
        "explanation": "Leaving early costs a full month's rent on top of the notice period.",
        "evidence": { "page": 3, "quote": "...", "verified": true } }
    ]
  }
}
```

Extra error: `413 file_too_large` also covers more than `CONTRACT_MAX_PAGES` pages, with a message that names the limit.

## Frontend: `/contracts`

- Same shell, notice bar and "waking up" handling as `/chat`. Add "Not legal advice." beside the results.
- One upload area. While the review runs, show the steps as they would happen ("Reading 12 pages", "Reviewing clauses", "Checking quotes") on a timer. The backend is one call, so this is approximate; keep it honest by not showing percentages.
- Results: summary and parties at the top, then key terms as a compact table, then risks (severity as a coloured label, not colour alone), then clauses grouped by kind.
- Each evidence item shows `p. N` and expands to the quote, with "Open page N" via the same blob-URL `#page=N` trick as `/chat`. Unverified items show "Quote not found in document" instead of a quote.
- "Download JSON" exports the review as a file.
- Ship a sample contract (a short invented lease or NDA, clearly fictional names) behind a "Try a sample contract" button, so a visitor can see a review without having a PDF handy.
- Mark the card on `/` live and link it.

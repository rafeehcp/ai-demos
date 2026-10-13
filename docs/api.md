# API contract: Chat with your docs

The contract reviewer's endpoint, `POST /api/contracts/review`, is specified in [contract-reviewer.md](contract-reviewer.md). It uses the same error shape and codes.

Base URL comes from `NEXT_PUBLIC_API_URL` on the frontend (for example `http://localhost:8000`). All bodies are JSON except the upload, which is `multipart/form-data`.

Every error response has this shape and a 4xx/5xx status:

```json
{ "error": { "code": "file_too_large", "message": "PDFs must be 10 MB or smaller." } }
```

`message` is written for the end user and the frontend shows it as-is.

| Status | `code` | When |
|---|---|---|
| 400 | `not_a_pdf` | Upload is not a PDF |
| 400 | `no_text` | PDF has no extractable text (for example a scanned image) |
| 400 | `empty_question` | Question is blank or longer than 1,000 characters |
| 404 | `session_not_found` | Session id unknown or expired |
| 409 | `too_many_documents` | Session already holds the maximum number of documents |
| 409 | `no_documents` | Asked a question before uploading anything |
| 413 | `file_too_large` | PDF over the size or page limit |
| 429 | `rate_limited` | Visitor exceeded the per-IP limit. Includes header `Retry-After: <seconds>` |
| 502 | `llm_error` | The LLM provider failed |
| 503 | `llm_quota` | The LLM provider returned 429 (free quota used up) |

## GET /api/health

`200 {"status": "ok"}`. Used by Render's health check and to wake the service.

## GET /api/config

Limits the UI shows to the visitor.

```json
{ "max_documents": 3, "max_file_mb": 10, "max_pages": 100, "contract_max_pages": 40, "provider_label": "Gemini 3.5 Flash" }
```

## POST /api/sessions

Creates an empty session. `201 {"session_id": "s_8f3k2..."}`. Sessions live in server memory and expire after `SESSION_TTL_MINUTES` of inactivity.

## POST /api/sessions/{session_id}/documents

Multipart field `file`. Extracts text per page, chunks it, embeds the chunks.

`201`:

```json
{ "id": "d_1a2b", "name": "lease.pdf", "pages": 12, "chunks": 31 }
```

## GET /api/sessions/{session_id}/documents

`200 {"documents": [Document, ...]}` in upload order.

## DELETE /api/sessions/{session_id}/documents/{document_id}

`204`. Removes the document and its chunks.

## POST /api/sessions/{session_id}/ask

Request:

```json
{ "question": "When can the tenant end the lease early?" }
```

Response `200`:

```json
{
  "answer": "The tenant can end the lease with 60 days' written notice after the first year [1]. An early-exit fee of one month's rent applies [2].",
  "citations": [
    { "n": 1, "document_id": "d_1a2b", "document_name": "lease.pdf", "page": 4, "quote": "…either party may terminate this agreement on sixty (60) days' written notice…" },
    { "n": 2, "document_id": "d_1a2b", "document_name": "lease.pdf", "page": 5, "quote": "…a termination fee equal to one (1) month's rent…" }
  ]
}
```

Rules:
- `[n]` markers in `answer` match `citations[].n`. Only sources the answer actually cites are returned, in order of first mention, renumbered from 1.
- `page` is 1-based and is the page the quoted text came from.
- `quote` is an excerpt of the retrieved chunk, at most 300 characters.
- When the documents don't contain the answer, `answer` says so plainly and `citations` is `[]`.
- Questions are single-turn. The server keeps no chat history.

# Design

A monorepo of small AI demos for a freelance portfolio. Demo 1 is **Chat with your docs**. Contract reviewer and Invoice → JSON come next and reuse `backend/app/core` and the frontend shell.

## Constraints

- Hosting: Render free tier for the API (512 MB RAM, one instance, sleeps when idle) and Vercel for the frontend.
- Cost: $0. The default LLM is Gemini's free tier through its OpenAI-compatible endpoint. Any OpenAI-compatible provider works by changing env vars.
- State is in memory and per session. Nothing is written to disk and nothing survives a restart. That's fine for a demo and keeps uploaded files from lingering.
- Public demo: every visitor sees "Demo only. Don't upload real or confidential documents." Uploads and questions are rate limited per IP.

## Data shape

```text
SessionStore            dict[session_id, Session], LRU-capped at MAX_SESSIONS, TTL-evicted
└─ Session
   ├─ id, last_used
   ├─ documents: list[Document]        upload order, at most MAX_DOCUMENTS
   └─ index: ChunkIndex
      ├─ chunks: list[Chunk]           Chunk = (document_id, document_name, page, text)
      └─ vectors: np.ndarray[float32]  shape (len(chunks), dim), rows L2-normalized
```

A `Chunk` never spans two pages, so every citation points at exactly one page. Chunks are about 1,000 characters with 150 characters of overlap, split on whitespace.

Retrieval is cosine similarity over the session's `vectors` (one matrix-vector product), top `TOP_K` chunks. At the limits (3 documents × 100 pages) a session holds at most a few hundred vectors, so numpy brute force beats adding a vector database.

## Provider

```python
class LLMProvider(Protocol):
    async def embed(self, texts: list[str]) -> np.ndarray: ...   # (len(texts), dim) float32
    async def complete(self, system: str, user: str) -> str: ...
```

- `OpenAICompatProvider` calls `{LLM_BASE_URL}/embeddings` and `{LLM_BASE_URL}/chat/completions` with httpx. It maps an upstream 429 to `LLMQuotaError` and any other failure to `LLMError`.
- `FakeProvider` is for tests and offline dev (`LLM_PROVIDER=fake`). Its embeddings are deterministic bag-of-words hashes, so related text really does score higher. Its answer cites source `[1]`.

## Answering

1. Embed the question and take the top `TOP_K` chunks.
2. Build a prompt listing them as numbered sources `[1]..[k]`, each labeled with document name and page.
3. The system prompt says: answer only from the sources, cite every claim with `[n]`, and say plainly when the sources don't answer it.
4. Parse the `[n]` markers in the reply. Drop any that point outside `1..k`. Renumber the cited sources from 1 in order of first mention, rewrite the markers to match, and return those sources as `citations`.

## Layout

```text
backend/
  app/
    main.py              FastAPI app, CORS, error handlers, mounts demo routers
    core/                shared by every demo
      config.py          Settings from env (pydantic-settings)
      errors.py          AppError(status, code, message) and the JSON error handler
      llm.py             LLMProvider, OpenAICompatProvider, FakeProvider, get_provider()
      pdf.py             extract_pages(bytes) -> list[str], with size/page/no-text checks
      ratelimit.py       per-IP sliding window, honors X-Forwarded-For
      sessions.py        Session, SessionStore
    demos/
      chat_docs/
        chunking.py      pages -> chunks
        index.py         ChunkIndex (add, remove_document, search)
        answer.py        prompt building and citation parsing
        router.py        the endpoints in docs/api.md
  tests/
frontend/                Next.js App Router, TypeScript
  app/
    page.tsx             demo index (one card per demo)
    chat/page.tsx        Chat with your docs
  lib/api.ts             typed client for docs/api.md
render.yaml              Render blueprint for the backend
```

## Limits (env-configurable defaults)

| Setting | Default |
|---|---|
| `MAX_SESSIONS` | 50 |
| `SESSION_TTL_MINUTES` | 30 |
| `MAX_DOCUMENTS` | 3 |
| `MAX_FILE_MB` | 10 |
| `MAX_PAGES` | 100 |
| `TOP_K` | 6 |
| `RATE_LIMIT_PER_MINUTE` | 10 (uploads and questions combined) |

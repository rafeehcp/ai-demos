# Backend

FastAPI service for the demos. Demo 1, Chat with your docs, implements [docs/api.md](../docs/api.md). State lives in memory, so a restart clears every session.

## Run locally

Set up once (Python 3.10 or 3.11):

```sh
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # macOS/Linux: .venv/bin/pip
```

Run offline with the fake model. It needs no API key:

```sh
LLM_PROVIDER=fake .venv/Scripts/uvicorn app.main:create_app --factory --reload
```

Run with Gemini. Copy `.env.example` to `.env` and set `LLM_API_KEY`, then:

```sh
.venv/Scripts/uvicorn app.main:create_app --factory --reload
```

The API listens on http://localhost:8000. Check it with `curl localhost:8000/api/health`.

## Environment variables

`.env.example` documents each one. The main ones:

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `openai_compat` | `fake` runs offline with deterministic embeddings and a canned answer. |
| `LLM_BASE_URL` | Gemini's OpenAI-compatible endpoint | Any OpenAI-compatible API. |
| `LLM_API_KEY` | none | Required unless `LLM_PROVIDER=fake`. The app refuses to start without it. |
| `CHAT_MODEL` | `gemini-3.5-flash,gemini-3.5-flash-lite,gemini-flash-latest` | Comma-separated fallback chain. When a model is overloaded, retired or out of quota, the next one answers. The first sets the label the UI shows. |
| `EMBED_MODEL` | `gemini-embedding-001` | |
| `EMBED_DIMENSIONS` | unset | Sent as `dimensions` when set. |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated frontend origins. |

Limits (`MAX_SESSIONS`, `SESSION_TTL_MINUTES`, `MAX_DOCUMENTS`, `MAX_FILE_MB`, `MAX_PAGES`, `TOP_K`, `RATE_LIMIT_PER_MINUTE`) default to the table in [docs/design.md](../docs/design.md).

## Tests

```sh
.venv/Scripts/python -m pytest
```

The tests use the fake provider and generate their PDFs, so they need no network access.

## Deploy

`render.yaml` at the repository root defines a free Render web service. Set `LLM_API_KEY` and `CORS_ORIGINS` in the Render dashboard.

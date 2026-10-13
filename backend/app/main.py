import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.core.llm import get_provider
from app.core.ratelimit import RateLimiter
from app.core.sessions import SessionStore
from app.demos.chat_docs.router import ChatState
from app.demos.chat_docs.router import router as chat_docs_router


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.llm_provider == "openai_compat" and not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY is required unless LLM_PROVIDER=fake.")
    logging.basicConfig(level=logging.INFO)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await app.state.llm.aclose()

    app = FastAPI(title="AI demos", lifespan=lifespan)
    app.state.settings = settings
    app.state.llm = get_provider(settings)
    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)
    app.state.chat_sessions = SessionStore(
        ChatState,
        max_sessions=settings.max_sessions,
        ttl_seconds=settings.session_ttl_minutes * 60,
    )

    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
        expose_headers=["Retry-After"],
    )

    @app.get("/api/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/config")
    async def config() -> dict:
        return {
            "max_documents": settings.max_documents,
            "max_file_mb": settings.max_file_mb,
            "max_pages": settings.max_pages,
            "contract_max_pages": settings.contract_max_pages,
            "provider_label": settings.provider_label,
        }

    app.include_router(chat_docs_router)
    return app

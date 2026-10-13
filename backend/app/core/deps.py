from fastapi import Request

from app.core.config import Settings
from app.core.llm import LLMProvider
from app.core.ratelimit import RateLimiter, client_ip


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_llm(request: Request) -> LLMProvider:
    return request.app.state.llm


def rate_limited(request: Request) -> None:
    """One limiter for every demo, so switching demos doesn't reset a visitor's budget."""
    limiter: RateLimiter = request.app.state.rate_limiter
    limiter.hit(client_ip(request))

import re
from functools import lru_cache
from typing import Literal, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_UPPERCASE_WORDS = {"gpt", "ai", "llm"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: Literal["openai_compat", "fake"] = "openai_compat"
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_api_key: str = ""
    # Comma-separated; later models are fallbacks when earlier ones are busy.
    chat_model: str = "gemini-3.5-flash,gemini-3.5-flash-lite,gemini-flash-latest"
    embed_model: str = "gemini-embedding-001"
    embed_dimensions: Optional[int] = None

    cors_origins: str = "http://localhost:3000"

    max_sessions: int = 50
    session_ttl_minutes: int = 30
    max_documents: int = 3
    max_file_mb: int = 10
    max_pages: int = 100
    contract_max_pages: int = 40
    invoice_max_files: int = 5
    invoice_max_pages: int = 5
    top_k: int = 6
    rate_limit_per_minute: int = 10

    @field_validator("embed_dimensions", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def chat_models(self) -> list[str]:
        return [m.strip() for m in self.chat_model.split(",") if m.strip()]

    @property
    def provider_label(self) -> str:
        if self.llm_provider == "fake":
            return "Offline fake model"
        return model_label(self.chat_models[0])


def model_label(model: str) -> str:
    """'gemini-3.8-flash' -> 'Gemini 3.8 Flash', 'models/gpt-4o-mini' -> 'GPT 4o Mini'."""
    name = model.rsplit("/", 1)[-1]
    words = [w for w in re.split(r"[-_\s]+", name) if w]
    return " ".join(
        w.upper() if w.lower() in _UPPERCASE_WORDS else w[:1].upper() + w[1:] for w in words
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

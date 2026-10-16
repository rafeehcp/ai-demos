import json
import logging
import re
import zlib
from typing import Callable, Mapping, Optional, Protocol, Sequence, TypeVar

import httpx
import numpy as np
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

EMBED_BATCH_SIZE = 100
FAKE_DIM = 256


class LLMError(AppError):
    def __init__(self, message: str = "The AI provider failed. Please try again.") -> None:
        super().__init__(502, "llm_error", message)


class LLMQuotaError(AppError):
    def __init__(self) -> None:
        super().__init__(
            503,
            "llm_quota",
            "The demo's free AI quota is used up for now. Please try again later.",
        )


class LLMBadJSON(LLMError):
    """The model replied, but not with a JSON object. `detail` says why, for a retry prompt."""

    def __init__(self, detail: str) -> None:
        super().__init__()
        self.detail = detail


class _ModelUnavailable(LLMError):
    """This model can't serve the request right now (overloaded, retired, timed out)."""


_UNAVAILABLE_STATUSES = {404, 500, 502, 503, 504}


class LLMProvider(Protocol):
    async def embed(self, texts: list[str]) -> np.ndarray: ...

    async def complete(self, system: str, user: str) -> str: ...

    async def complete_json(self, system: str, user: str, images: Sequence[str] = ()) -> dict:
        """`images` are data URLs, sent after the text in the user message."""
        ...

    async def aclose(self) -> None: ...


Model = TypeVar("Model", bound=BaseModel)

_RETRY_NOTE = "\n\nYour previous reply was rejected: {problem}\nReply again with one JSON object that follows the rules."
_MAX_ERRORS_IN_RETRY = 8


async def complete_validated(
    llm: LLMProvider, schema: type[Model], system: str, user: str, images: Sequence[str] = ()
) -> Model:
    """A JSON-mode reply parsed into `schema`. A malformed reply is retried once with the reason appended."""
    prompt = user
    for attempt in (1, 2):
        try:
            return schema.model_validate(await llm.complete_json(system, prompt, images))
        except LLMBadJSON as exc:
            problem = exc.detail
        except ValidationError as exc:
            problem = describe_validation_error(exc)
        logger.warning("%s attempt %d rejected: %s", schema.__name__, attempt, problem)
        prompt = user + _RETRY_NOTE.format(problem=problem)
    raise LLMError("The AI model returned a reply the app couldn't read. Please try again.")


def describe_validation_error(exc: ValidationError) -> str:
    errors = exc.errors(include_url=False)
    parts = [
        f"{'.'.join(str(p) for p in e['loc']) or 'reply'}: {e['msg']}" for e in errors[:_MAX_ERRORS_IN_RETRY]
    ]
    if len(errors) > _MAX_ERRORS_IN_RETRY:
        parts.append(f"and {len(errors) - _MAX_ERRORS_IN_RETRY} more")
    return "; ".join(parts)


class OpenAICompatProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        chat_models: Sequence[str],
        embed_model: str,
        embed_dimensions: Optional[int] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self._chat_models = list(chat_models)
        self._embed_model = embed_model
        self._embed_dimensions = embed_dimensions
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(30.0, connect=10.0),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def embed(self, texts: list[str]) -> np.ndarray:
        rows: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[start : start + EMBED_BATCH_SIZE]
            body: dict = {"model": self._embed_model, "input": batch}
            if self._embed_dimensions is not None:
                body["dimensions"] = self._embed_dimensions
            data = await self._post("embeddings", body)
            try:
                # Gemini's OpenAI-compatible endpoint omits "index" and returns input order.
                ranked = sorted(enumerate(data["data"]), key=lambda pair: pair[1].get("index", pair[0]))
                vectors = [item["embedding"] for _, item in ranked]
            except (KeyError, TypeError) as exc:
                raise LLMError() from exc
            if len(vectors) != len(batch):
                logger.error("embeddings: sent %d inputs, got %d vectors", len(batch), len(vectors))
                raise LLMError()
            rows.extend(vectors)
        return np.asarray(rows, dtype=np.float32)

    async def complete(self, system: str, user: str) -> str:
        return await self._first_available(system, user, json_mode=False)

    async def complete_json(self, system: str, user: str, images: Sequence[str] = ()) -> dict:
        content = await self._first_available(system, _user_content(user, images), json_mode=True)
        try:
            data = json.loads(content)
        except ValueError as exc:
            raise LLMBadJSON(f"The reply was not valid JSON ({exc}).") from exc
        if not isinstance(data, dict):
            raise LLMBadJSON("The reply was JSON but not an object.")
        return data

    async def _first_available(self, system: str, user: str | list[dict], *, json_mode: bool) -> str:
        # Free tiers overload or rate-limit individual models, so fall through the list.
        failures: list[LLMError] = []
        for model in self._chat_models:
            try:
                return await self._complete_with(model, system, user, json_mode=json_mode)
            except (_ModelUnavailable, LLMQuotaError) as exc:
                logger.warning("chat model %s unavailable, trying next: %s", model, exc.code)
                failures.append(exc)
        if failures and all(isinstance(f, LLMQuotaError) for f in failures):
            raise LLMQuotaError()
        raise LLMError("The AI model is busy right now. Please try again in a minute.")

    async def _complete_with(self, model: str, system: str, user: str | list[dict], *, json_mode: bool) -> str:
        body: dict = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        data = await self._post("chat/completions", body)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError() from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError()
        return content.strip()

    async def _post(self, path: str, body: dict) -> dict:
        try:
            response = await self._client.post(path, json=body)
        except httpx.TimeoutException as exc:
            logger.warning("LLM request to %s timed out", path)
            raise _ModelUnavailable() from exc
        except httpx.HTTPError as exc:
            logger.warning("LLM request to %s failed: %r", path, exc)
            raise LLMError() from exc
        if response.status_code == 429:
            raise LLMQuotaError()
        if response.status_code in _UNAVAILABLE_STATUSES:
            logger.warning(
                "LLM %s returned %d: %s", path, response.status_code, response.text[:300]
            )
            raise _ModelUnavailable()
        if response.is_error:
            logger.warning(
                "LLM %s returned %d: %s", path, response.status_code, response.text[:500]
            )
            raise LLMError()
        try:
            return response.json()
        except ValueError as exc:
            raise LLMError() from exc


def _user_content(text: str, images: Sequence[str]) -> str | list[dict]:
    if not images:
        return text
    return [{"type": "text", "text": text}] + [{"type": "image_url", "image_url": {"url": url}} for url in images]


FakeJSONReply = Callable[[str], dict]


class FakeProvider:
    """Offline provider. Embeddings are hashed bag-of-words, so texts that share
    words really do score higher; the answer always cites source [1].
    complete_json answers with the reply registered for the system prompt."""

    def __init__(self, json_replies: Optional[Mapping[str, FakeJSONReply]] = None) -> None:
        self._json_replies = dict(json_replies or {})

    async def aclose(self) -> None:
        pass

    async def embed(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), FAKE_DIM), dtype=np.float32)
        for row, text in enumerate(texts):
            for token in re.findall(r"\w+", text.lower()):
                vectors[row, zlib.crc32(token.encode()) % FAKE_DIM] += 1.0
        return vectors

    async def complete(self, system: str, user: str) -> str:
        return "This offline demo answer is drawn from the most relevant passage [1]."

    async def complete_json(self, system: str, user: str, images: Sequence[str] = ()) -> dict:
        return self._json_replies[system](user)


def get_provider(settings: Settings, fake_json_replies: Mapping[str, FakeJSONReply]) -> LLMProvider:
    if settings.llm_provider == "fake":
        return FakeProvider(fake_json_replies)
    return OpenAICompatProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        chat_models=settings.chat_models,
        embed_model=settings.embed_model,
        embed_dimensions=settings.embed_dimensions,
    )

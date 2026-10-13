import json

import httpx
import numpy as np
import pytest

from app.core.config import model_label
from app.core.llm import FakeProvider, LLMError, LLMQuotaError, OpenAICompatProvider

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def provider(handler, **kwargs) -> OpenAICompatProvider:
    return OpenAICompatProvider(
        base_url=BASE_URL,
        api_key="sk-test",
        chat_model="gemini-2.5-flash",
        embed_model="gemini-embedding-001",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


@pytest.mark.anyio
async def test_embeddings_are_batched_and_keep_input_order():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        # Returned out of order on purpose: the provider must sort by index.
        data = [
            {"index": i, "embedding": [float(text.split("-")[1]), 1.0]}
            for i, text in reversed(list(enumerate(body["input"])))
        ]
        return httpx.Response(200, json={"data": data})

    p = provider(handler, embed_dimensions=768)
    vectors = await p.embed([f"t-{i}" for i in range(250)])
    await p.aclose()

    assert vectors.shape == (250, 2) and vectors.dtype == np.float32
    assert vectors[:, 0].tolist() == list(range(250))
    assert [len(json.loads(r.content)["input"]) for r in requests] == [100, 100, 50]
    for r in requests:
        assert str(r.url) == BASE_URL + "embeddings"
        assert r.headers["authorization"] == "Bearer sk-test"
        body = json.loads(r.content)
        assert body["model"] == "gemini-embedding-001"
        assert body["dimensions"] == 768


@pytest.mark.anyio
async def test_dimensions_omitted_when_unset():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})

    await provider(handler).embed(["x"])
    assert "dimensions" not in bodies[0]


@pytest.mark.anyio
async def test_complete_sends_system_and_user_messages():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": " Answer [1]. "}}]})

    reply = await provider(handler).complete("sys", "usr")

    assert reply == "Answer [1]."
    assert seen["url"] == BASE_URL + "chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"]["model"] == "gemini-2.5-flash"
    assert seen["body"]["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "usr"},
    ]


@pytest.mark.anyio
async def test_upstream_429_is_quota_error():
    p = provider(lambda r: httpx.Response(429, json={"error": "quota"}))
    with pytest.raises(LLMQuotaError) as exc:
        await p.complete("s", "u")
    assert (exc.value.status, exc.value.code) == (503, "llm_quota")
    with pytest.raises(LLMQuotaError):
        await p.embed(["x"])


@pytest.mark.anyio
@pytest.mark.parametrize(
    "handler",
    [
        lambda r: httpx.Response(500, text="boom"),
        lambda r: httpx.Response(401, json={"error": "bad key"}),
        lambda r: httpx.Response(200, text="not json"),
        lambda r: httpx.Response(200, json={"choices": []}),
    ],
)
async def test_other_failures_are_llm_error(handler):
    with pytest.raises(LLMError) as exc:
        await provider(handler).complete("s", "u")
    assert (exc.value.status, exc.value.code) == (502, "llm_error")


@pytest.mark.anyio
async def test_network_failure_is_llm_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(LLMError):
        await provider(handler).embed(["x"])


@pytest.mark.anyio
async def test_fake_embeddings_score_related_text_higher():
    vectors = await FakeProvider().embed(
        ["termination notice period", "the notice period for termination", "pet policy and parking"]
    )
    unit = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    assert unit[0] @ unit[1] > unit[0] @ unit[2]


def test_provider_label_from_model_name():
    assert model_label("gemini-2.5-flash") == "Gemini 2.5 Flash"
    assert model_label("models/gpt-4o-mini") == "GPT 4o Mini"

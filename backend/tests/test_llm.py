import json

import httpx
import numpy as np
import pytest

from app.core.config import model_label
from app.core.llm import FakeProvider, LLMBadJSON, LLMError, LLMQuotaError, OpenAICompatProvider

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def provider(handler, **kwargs) -> OpenAICompatProvider:
    return OpenAICompatProvider(
        base_url=BASE_URL,
        api_key="sk-test",
        chat_models=kwargs.pop("chat_models", ["gemini-3.8-flash"]),
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
async def test_embeddings_without_index_keep_response_order():
    def handler(request: httpx.Request) -> httpx.Response:
        texts = json.loads(request.content)["input"]
        return httpx.Response(200, json={"data": [{"embedding": [float(len(t)), 1.0]} for t in texts]})

    vectors = await provider(handler).embed(["a", "bbb", "cc"])
    assert vectors[:, 0].tolist() == [1.0, 3.0, 2.0]


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
    assert seen["body"]["model"] == "gemini-3.8-flash"
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
    assert model_label("gemini-3.8-flash") == "Gemini 3.8 Flash"
    assert model_label("models/gpt-4o-mini") == "GPT 4o Mini"


def _chat_reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


@pytest.mark.anyio
@pytest.mark.parametrize("failure", [503, 404, 429, "timeout"])
async def test_busy_chat_model_falls_back_to_next(failure):
    tried = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        tried.append(model)
        if model == "busy-model":
            if failure == "timeout":
                raise httpx.ReadTimeout("slow", request=request)
            return httpx.Response(failure, json={"error": {}})
        return _chat_reply("from backup")

    answer = await provider(handler, chat_models=["busy-model", "backup-model"]).complete("s", "u")
    assert answer == "from backup"
    assert tried == ["busy-model", "backup-model"]


@pytest.mark.anyio
async def test_all_chat_models_busy_is_llm_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": {}})

    with pytest.raises(LLMError) as exc:
        await provider(handler, chat_models=["a", "b"]).complete("s", "u")
    assert exc.value.code == "llm_error"


@pytest.mark.anyio
async def test_all_chat_models_out_of_quota_is_quota_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {}})

    with pytest.raises(LLMQuotaError):
        await provider(handler, chat_models=["a", "b"]).complete("s", "u")


@pytest.mark.anyio
async def test_auth_failure_does_not_try_other_models():
    tried = []

    def handler(request: httpx.Request) -> httpx.Response:
        tried.append(json.loads(request.content)["model"])
        return httpx.Response(401, json={"error": {}})

    with pytest.raises(LLMError):
        await provider(handler, chat_models=["a", "b"]).complete("s", "u")
    assert tried == ["a"]


def test_chat_model_list_and_label_use_first_model():
    from app.core.config import Settings

    settings = Settings(_env_file=None, chat_model=" gemini-3.5-flash , gemini-3.5-flash-lite ")
    assert settings.chat_models == ["gemini-3.5-flash", "gemini-3.5-flash-lite"]
    assert settings.provider_label == "Gemini 3.5 Flash"


@pytest.mark.anyio
async def test_complete_json_asks_for_json_mode_and_parses_the_object():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return _chat_reply('{"summary": "ok", "risks": []}')

    data = await provider(handler).complete_json("sys", "usr")

    assert data == {"summary": "ok", "risks": []}
    assert bodies[0]["response_format"] == {"type": "json_object"}
    assert bodies[0]["messages"][0] == {"role": "system", "content": "sys"}


@pytest.mark.anyio
async def test_plain_complete_does_not_ask_for_json_mode():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return _chat_reply("prose")

    await provider(handler).complete("s", "u")
    assert "response_format" not in bodies[0]


@pytest.mark.anyio
async def test_complete_json_falls_back_when_a_model_is_busy():
    tried = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        tried.append((body["model"], body["response_format"]["type"]))
        if body["model"] == "busy-model":
            return httpx.Response(503, json={"error": {}})
        return _chat_reply('{"from": "backup"}')

    data = await provider(handler, chat_models=["busy-model", "backup-model"]).complete_json("s", "u")
    assert data == {"from": "backup"}
    assert tried == [("busy-model", "json_object"), ("backup-model", "json_object")]


@pytest.mark.anyio
@pytest.mark.parametrize("content", ["not json at all", "[1, 2]", '{"cut": "off'])
async def test_complete_json_reports_non_object_replies(content):
    with pytest.raises(LLMBadJSON) as exc:
        await provider(lambda r: _chat_reply(content)).complete_json("s", "u")
    assert (exc.value.status, exc.value.code) == (502, "llm_error")
    assert exc.value.detail


@pytest.mark.anyio
async def test_complete_json_sends_images_as_data_url_parts_after_the_text():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return _chat_reply('{"ok": true}')

    images = ["data:image/png;base64,iVBORw0KGgo=", "data:image/jpeg;base64,/9j/4AAQ"]
    await provider(handler).complete_json("sys", "read these", images)

    assert bodies[0]["messages"][1] == {
        "role": "user",
        "content": [
            {"type": "text", "text": "read these"},
            {"type": "image_url", "image_url": {"url": images[0]}},
            {"type": "image_url", "image_url": {"url": images[1]}},
        ],
    }
    assert bodies[0]["response_format"] == {"type": "json_object"}


@pytest.mark.anyio
async def test_fake_json_reply_is_chosen_by_system_prompt():
    fake = FakeProvider({"a": lambda user: {"from": "a", "user": user}, "b": lambda user: {"from": "b"}})
    assert await fake.complete_json("a", "hi", ["data:image/png;base64,x"]) == {"from": "a", "user": "hi"}
    assert await fake.complete_json("b", "hi") == {"from": "b"}

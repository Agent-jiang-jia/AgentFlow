"""OpenAI-compatible streaming model client tests."""

import json

import httpx
import pytest
from app.core.config import Settings
from app.services.model_client import ModelClientError, ModelMessage, OpenAICompatibleChatModel


@pytest.mark.anyio
async def test_model_client_streams_openai_compatible_deltas() -> None:
    """The configured fixed model receives ordered context and yields text only."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://model.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer secret-value"
        payload = json.loads(request.content)
        assert payload == {
            "model": "fixed-model",
            "messages": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "请继续"},
            ],
            "stream": True,
        }
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=(
                b'data: {"choices":[{"delta":{"content":"one"}}]}\n\n'
                b'data: {"choices":[{"delta":{"content":" two"}}]}\n\n'
                b"data: [DONE]\n\n"
            ),
        )

    settings = Settings(
        _env_file=None,
        model_api_base="https://model.example/v1/",
        model_api_key="secret-value",
        model_name="fixed-model",
    )
    model = OpenAICompatibleChatModel(
        settings,
        transport=httpx.MockTransport(handler),
    )

    chunks = [
        chunk
        async for chunk in model.stream(
            (
                ModelMessage(role="user", content="你好"),
                ModelMessage(role="assistant", content="请继续"),
            )
        )
    ]

    assert chunks == ["one", " two"]


@pytest.mark.anyio
async def test_model_client_converts_configuration_and_provider_failures() -> None:
    """Missing configuration and upstream HTTP errors use one internal safe error."""
    unconfigured = OpenAICompatibleChatModel(Settings(_env_file=None))
    with pytest.raises(ModelClientError):
        _ = [chunk async for chunk in unconfigured.stream(())]

    settings = Settings(
        _env_file=None,
        model_api_base="https://model.example/v1",
        model_name="fixed-model",
    )
    unavailable = OpenAICompatibleChatModel(
        settings,
        transport=httpx.MockTransport(lambda _request: httpx.Response(503)),
    )
    with pytest.raises(ModelClientError):
        _ = [chunk async for chunk in unavailable.stream((ModelMessage("user", "hello"),))]

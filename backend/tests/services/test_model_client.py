"""OpenAI-compatible streaming model client tests."""

import json

import httpx
import pytest
from app.core.config import Settings
from app.services.model_client import (
    ModelClientError,
    OpenAICompatibleChatModel,
)
from app.tools.base import ToolDefinition
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


@pytest.mark.anyio
async def test_model_client_streams_text_and_tool_call_deltas() -> None:
    """The fixed model receives ordered tool context and yields both delta types."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://model.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer secret-value"
        payload = json.loads(request.content)
        assert payload == {
            "model": "fixed-model",
            "messages": [
                {"role": "user", "content": "现在几点?"},
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "server-call-id",
                            "type": "function",
                            "function": {
                                "name": "get_current_time",
                                "arguments": '{"timezone":"UTC"}',
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "content": '{"success":true}',
                    "tool_call_id": "server-call-id",
                },
            ],
            "stream": True,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_current_time",
                        "description": "Get time",
                        "parameters": {"type": "object"},
                    },
                }
            ],
        }
        return httpx.Response(
            200,
            headers={"Content-Type": "text/event-stream"},
            content=(
                b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"provider-",'
                b'"function":{"name":"get_current_","arguments":"{\\"timezone\\":"}}]}}]}\n\n'
                b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call",'
                b'"function":{"name":"time","arguments":"\\"UTC\\"}"}}]}}]}\n\n'
                b'data: {"choices":[{"delta":{"content":"It is noon."}}]}\n\n'
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
    assistant = AIMessage(
        content="",
        additional_kwargs={
            "tool_calls": [
                {
                    "id": "server-call-id",
                    "type": "function",
                    "function": {
                        "name": "get_current_time",
                        "arguments": '{"timezone":"UTC"}',
                    },
                }
            ]
        },
    )
    chunks = [
        chunk
        async for chunk in model.stream(
            (
                HumanMessage(content="现在几点?"),
                assistant,
                ToolMessage(content='{"success":true}', tool_call_id="server-call-id"),
            ),
            (
                ToolDefinition(
                    name="get_current_time",
                    description="Get time",
                    parameters={"type": "object"},
                ),
            ),
        )
    ]

    assert chunks[0].tool_calls[0].name == "get_current_"
    assert chunks[1].tool_calls[0].arguments == '"UTC"}'
    assert chunks[2].content == "It is noon."


@pytest.mark.anyio
async def test_model_client_converts_configuration_and_provider_failures() -> None:
    """Missing configuration and upstream HTTP errors use one internal safe error."""
    unconfigured = OpenAICompatibleChatModel(Settings(_env_file=None))
    with pytest.raises(ModelClientError):
        _ = [chunk async for chunk in unconfigured.stream((), ())]

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
        _ = [
            chunk
            async for chunk in unavailable.stream(
                (HumanMessage(content="hello"),),
                (),
            )
        ]

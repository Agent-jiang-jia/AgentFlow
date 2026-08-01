"""Streaming client for the configured fixed tool-capable chat model."""

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from app.core.config import Settings
from app.tools.base import ToolDefinition


class ModelClientError(Exception):
    """Internal model transport or protocol failure."""


@dataclass(frozen=True, slots=True)
class ModelToolCallDelta:
    """One streamed fragment of a provider tool call."""

    index: int
    provider_id: str
    name: str
    arguments: str


@dataclass(frozen=True, slots=True)
class ModelStreamChunk:
    """Provider-neutral assistant text and tool-call deltas."""

    content: str = ""
    tool_calls: tuple[ModelToolCallDelta, ...] = ()


class ChatModel(Protocol):
    """The streaming model surface required by the Phase 3 agent."""

    def stream(
        self,
        messages: Sequence[BaseMessage],
        tools: Sequence[ToolDefinition],
    ) -> AsyncIterator[ModelStreamChunk]:
        """Yield assistant text and tool-call deltas for one model turn."""
        ...


class OpenAICompatibleChatModel:
    """Call one configured OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_base = settings.model_api_base.strip().rstrip("/")
        self._api_key = (
            settings.model_api_key.get_secret_value() if settings.model_api_key is not None else ""
        )
        self._model_name = settings.model_name.strip()
        self._timeout = settings.model_timeout_seconds
        self._transport = transport

    def _endpoint(self) -> str:
        if not self._api_base or not self._model_name:
            raise ModelClientError("Model endpoint is not configured")
        if self._api_base.endswith("/chat/completions"):
            return self._api_base
        return f"{self._api_base}/chat/completions"

    async def stream(
        self,
        messages: Sequence[BaseMessage],
        tools: Sequence[ToolDefinition],
    ) -> AsyncIterator[ModelStreamChunk]:
        """Yield content and function-call deltas from an OpenAI-compatible stream."""
        headers = {"Accept": "text/event-stream", "Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload: dict[str, object] = {
            "model": self._model_name,
            "messages": [self._serialize_message(message) for message in messages],
            "stream": True,
        }
        if tools:
            payload["tools"] = [tool.as_openai_tool() for tool in tools]

        try:
            async with (
                httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client,
                client.stream(
                    "POST",
                    self._endpoint(),
                    headers=headers,
                    json=payload,
                ) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    yield self._stream_chunk(data)
        except ModelClientError:
            raise
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ModelClientError("Model request failed") from exc

    @classmethod
    def _serialize_message(cls, message: BaseMessage) -> dict[str, object]:
        content = cls._text_content(message)
        if isinstance(message, HumanMessage):
            return {"role": "user", "content": content}
        if isinstance(message, SystemMessage):
            return {"role": "system", "content": content}
        if isinstance(message, ToolMessage):
            return {
                "role": "tool",
                "content": content,
                "tool_call_id": message.tool_call_id,
            }
        if isinstance(message, AIMessage):
            payload: dict[str, object] = {"role": "assistant", "content": content}
            tool_calls = message.additional_kwargs.get("tool_calls")
            if isinstance(tool_calls, list) and tool_calls:
                payload["tool_calls"] = tool_calls
            return payload
        raise ModelClientError("Unsupported model message role")

    @staticmethod
    def _text_content(message: BaseMessage) -> str:
        if not isinstance(message.content, str):
            raise ModelClientError("Non-text model messages are not supported")
        return message.content

    @staticmethod
    def _stream_chunk(data: str) -> ModelStreamChunk:
        payload = json.loads(data)
        choices = payload["choices"]
        if not isinstance(choices, list) or not choices:
            return ModelStreamChunk()
        choice = choices[0]
        if not isinstance(choice, Mapping):
            raise TypeError("Invalid model choice")
        delta = choice.get("delta", {})
        if not isinstance(delta, Mapping):
            raise TypeError("Invalid model delta")

        content = delta.get("content", "")
        if content is None:
            content = ""
        if not isinstance(content, str):
            raise TypeError("Invalid model content")

        raw_tool_calls = delta.get("tool_calls", [])
        if raw_tool_calls is None:
            raw_tool_calls = []
        if not isinstance(raw_tool_calls, list):
            raise TypeError("Invalid model tool calls")
        tool_call_deltas = tuple(
            OpenAICompatibleChatModel._tool_call_delta(item) for item in raw_tool_calls
        )
        return ModelStreamChunk(content=content, tool_calls=tool_call_deltas)

    @staticmethod
    def _tool_call_delta(raw_call: object) -> ModelToolCallDelta:
        if not isinstance(raw_call, Mapping):
            raise TypeError("Invalid model tool call")
        index = raw_call.get("index")
        if not isinstance(index, int) or index < 0:
            raise TypeError("Invalid model tool call index")
        provider_id = raw_call.get("id", "")
        if provider_id is None:
            provider_id = ""
        if not isinstance(provider_id, str):
            raise TypeError("Invalid model tool call id")
        function = raw_call.get("function", {})
        if not isinstance(function, Mapping):
            raise TypeError("Invalid model function call")
        name = function.get("name", "")
        arguments = function.get("arguments", "")
        if name is None:
            name = ""
        if arguments is None:
            arguments = ""
        if not isinstance(name, str) or not isinstance(arguments, str):
            raise TypeError("Invalid model function call fields")
        return ModelToolCallDelta(
            index=index,
            provider_id=provider_id,
            name=name,
            arguments=arguments,
        )

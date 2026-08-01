"""Streaming client for the configured fixed chat model."""

import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings


class ModelClientError(Exception):
    """Internal model transport or protocol failure."""


@dataclass(frozen=True, slots=True)
class ModelMessage:
    """A role/content pair sent to the plain chat model."""

    role: str
    content: str


class ChatModel(Protocol):
    """The minimal streaming model surface required by Phase 2."""

    def stream(self, messages: Sequence[ModelMessage]) -> AsyncIterator[str]:
        """Yield text deltas for one model response."""
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

    async def stream(self, messages: Sequence[ModelMessage]) -> AsyncIterator[str]:
        """Yield content deltas from an OpenAI-compatible SSE response."""
        headers = {"Accept": "text/event-stream", "Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        payload = {
            "model": self._model_name,
            "messages": [
                {"role": message.role, "content": message.content} for message in messages
            ],
            "stream": True,
        }

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
                    yield self._content_delta(data)
        except ModelClientError:
            raise
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ModelClientError("Model request failed") from exc

    @staticmethod
    def _content_delta(data: str) -> str:
        payload = json.loads(data)
        choices = payload["choices"]
        if not isinstance(choices, list) or not choices:
            return ""
        choice = choices[0]
        if not isinstance(choice, dict):
            raise TypeError("Invalid model choice")
        delta = choice.get("delta", {})
        if not isinstance(delta, dict):
            raise TypeError("Invalid model delta")
        content = delta.get("content", "")
        if content is None:
            return ""
        if not isinstance(content, str):
            raise TypeError("Invalid model content")
        return content

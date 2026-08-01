"""Phase 4 web-tool loop, source persistence, and public projection tests."""

import json
from collections.abc import AsyncIterator, Sequence
from typing import cast

import httpx
import pytest
from app.core.config import Settings
from app.db.database import Database
from app.db.models.source import Source
from app.main import create_app
from app.services.model_client import (
    ModelStreamChunk,
    ModelToolCallDelta,
)
from app.services.web_fetch_service import WebFetchService
from app.services.web_search_service import WebSearchService
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import BaseMessage
from pydantic import SecretStr
from sqlalchemy import select


def parse_sse(body: str) -> list[dict[str, object]]:
    """Decode test SSE frames into JSON payloads."""
    events: list[dict[str, object]] = []
    for frame in body.strip().split("\n\n"):
        data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
        payload = json.loads(data_line.removeprefix("data: "))
        assert isinstance(payload, dict)
        events.append(payload)
    return events


def tool_chunk(name: str, arguments: dict[str, object]) -> ModelToolCallDelta:
    """Create one complete model function call."""
    return ModelToolCallDelta(
        index=0,
        provider_id="provider-call",
        name=name,
        arguments=json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
    )


class ScriptedModel:
    """Return one deterministic sequence for each model loop."""

    def __init__(self, turns: Sequence[Sequence[ModelStreamChunk]]) -> None:
        self.turns = tuple(tuple(turn) for turn in turns)
        self.call_count = 0

    async def stream(
        self,
        messages: Sequence[BaseMessage],
        tools: Sequence[object],
    ) -> AsyncIterator[ModelStreamChunk]:
        assert messages
        assert tools
        turn = self.turns[self.call_count]
        self.call_count += 1
        for chunk in turn:
            yield chunk


async def public_resolver(_host: str, _port: int) -> Sequence[str]:
    """Resolve test hostnames to a public example address."""
    return ("93.184.216.34",)


@pytest.mark.anyio
async def test_search_then_fetch_promotes_and_displays_actual_source(
    migrated_settings: Settings,
) -> None:
    """A used URL is de-duplicated, promoted, persisted, streamed, and restored."""
    model = ScriptedModel(
        (
            (ModelStreamChunk(tool_calls=(tool_chunk("web_search", {"query": "智能体框架"}),)),),
            (
                ModelStreamChunk(
                    tool_calls=(
                        tool_chunk(
                            "web_fetch",
                            {"url": "https://public.example/article", "max_chars": 2000},
                        ),
                    )
                ),
            ),
            (ModelStreamChunk(content="已根据检索和网页正文完成总结。"),),
        )
    )
    app = create_app(migrated_settings)
    app.state.model_client = model
    app.state.web_search_service = WebSearchService(
        provider="tavily",
        api_base="https://search.example/api",
        api_key=SecretStr("provider-test-secret"),
        timeout_seconds=2,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "title": "Search title",
                            "url": "https://public.example/article#result",
                            "content": "Search snippet",
                        }
                    ]
                },
            )
        ),
    )
    app.state.web_fetch_service = WebFetchService(
        timeout_seconds=2,
        max_bytes=100_000,
        resolver=public_resolver,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200,
                headers={"content-type": "text/html; charset=utf-8"},
                content=(
                    b"<html><head><title>Fetched title</title></head>"
                    b"<body><article><h1>Heading</h1><p>Verified article body.</p>"
                    b"</article></body></html>"
                ),
            )
        ),
    )

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        response = await client.post(
            f"/api/threads/{thread_id}/chat/stream",
            json={"message": "搜索并读取资料"},
        )
        events = parse_sse(response.text)
        history = (await client.get(f"/api/threads/{thread_id}/messages")).json()

    assert response.status_code == 200
    assert "provider-test-secret" not in response.text
    tool_results = [event for event in events if event["event"] == "tool_result"]
    assert [cast(dict[str, object], event["data"])["success"] for event in tool_results] == [
        True,
        True,
    ]
    assistant_end = next(event for event in events if event["event"] == "assistant_end")
    streamed_sources = cast(dict[str, object], assistant_end["data"])["sources"]
    assert streamed_sources == [
        {
            "title": "Fetched title",
            "url": "https://public.example/article",
            "snippet": "Heading\n\nVerified article body.",
            "source_type": "web_page",
        }
    ]
    assert history["items"][-1]["metadata"]["sources"] == streamed_sources

    database = cast(Database, app.state.database)
    with database.session_factory() as session:
        sources = list(session.scalars(select(Source).where(Source.thread_id == thread_id)))
        assert len(sources) == 1
        assert sources[0].source_type == "web_page"


@pytest.mark.anyio
async def test_private_fetch_is_a_safe_tool_error_and_agent_can_continue(
    migrated_settings: Settings,
) -> None:
    """SSRF rejection is returned to the model without crashing the run."""
    model = ScriptedModel(
        (
            (
                ModelStreamChunk(
                    tool_calls=(tool_chunk("web_fetch", {"url": "http://127.0.0.1/admin"}),)
                ),
            ),
            (ModelStreamChunk(content="该地址不允许访问。"),),
        )
    )
    app = create_app(migrated_settings)
    app.state.model_client = model

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        response = await client.post(
            f"/api/threads/{thread_id}/chat/stream",
            json={"message": "读取本机管理页"},
        )
        events = parse_sse(response.text)

    tool_result = next(event for event in events if event["event"] == "tool_result")
    data = cast(dict[str, object], tool_result["data"])
    assert data["success"] is False
    assert data["error"] == {
        "code": "URL_NOT_ALLOWED",
        "message": "URL 不允许访问",
        "retryable": False,
    }
    assert cast(dict[str, object], events[-1]["data"])["status"] == "success"
    assert "127.0.0.1" not in response.text

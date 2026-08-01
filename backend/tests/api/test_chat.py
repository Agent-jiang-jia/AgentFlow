"""Streaming single-agent API, protection, and persistence tests."""

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from typing import cast

import pytest
from app.agent.runtime import AgentRuntime
from app.core.config import Settings
from app.db.database import Database
from app.db.models.run import Run
from app.db.models.tool_call import ToolCall
from app.main import create_app
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.model_client import (
    ChatModel,
    ModelClientError,
    ModelStreamChunk,
    ModelToolCallDelta,
)
from app.tools import create_phase_three_registry
from app.tools.base import Tool, ToolContext, ToolDefinition, ToolOutput
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select


def parse_sse(body: str) -> list[dict[str, object]]:
    """Decode test SSE frames into their JSON payloads."""
    events: list[dict[str, object]] = []
    for frame in body.strip().split("\n\n"):
        data_line = next(line for line in frame.splitlines() if line.startswith("data: "))
        payload = json.loads(data_line.removeprefix("data: "))
        assert isinstance(payload, dict)
        events.append(payload)
    return events


def tool_chunk(
    name: str,
    arguments: dict[str, object],
    *,
    index: int = 0,
) -> ModelToolCallDelta:
    """Create one complete function call as a single provider delta."""
    return ModelToolCallDelta(
        index=index,
        provider_id=f"provider-{index}",
        name=name,
        arguments=json.dumps(arguments, ensure_ascii=False, separators=(",", ":")),
    )


class RecordingModel:
    """Deterministic direct-answer model that records every received context."""

    def __init__(self, response: str = "你好世界") -> None:
        self.response = response
        self.contexts: list[tuple[BaseMessage, ...]] = []
        self.tool_definitions: list[tuple[ToolDefinition, ...]] = []

    async def stream(
        self,
        messages: Sequence[BaseMessage],
        tools: Sequence[ToolDefinition],
    ) -> AsyncIterator[ModelStreamChunk]:
        self.contexts.append(tuple(messages))
        self.tool_definitions.append(tuple(tools))
        midpoint = max(1, len(self.response) // 2)
        yield ModelStreamChunk(content=self.response[:midpoint])
        yield ModelStreamChunk(content=self.response[midpoint:])


class ScriptedModel:
    """Return one deterministic sequence for each successive model loop."""

    def __init__(self, turns: Sequence[Sequence[ModelStreamChunk]]) -> None:
        self.turns = tuple(tuple(turn) for turn in turns)
        self.contexts: list[tuple[BaseMessage, ...]] = []

    async def stream(
        self,
        messages: Sequence[BaseMessage],
        tools: Sequence[ToolDefinition],
    ) -> AsyncIterator[ModelStreamChunk]:
        assert tools
        turn_index = len(self.contexts)
        self.contexts.append(tuple(messages))
        if turn_index >= len(self.turns):
            raise ModelClientError("Script exhausted")
        for chunk in self.turns[turn_index]:
            yield chunk


class FailingModel:
    """Model double that fails before producing a content delta."""

    async def stream(
        self,
        messages: Sequence[BaseMessage],
        tools: Sequence[ToolDefinition],
    ) -> AsyncIterator[ModelStreamChunk]:
        assert messages
        assert tools
        if False:
            yield ModelStreamChunk()
        raise ModelClientError("provider unavailable")


def make_service(
    *,
    database: Database,
    settings: Settings,
    model: ChatModel,
    registry: ToolRegistry | None = None,
    timeout_seconds: float | None = None,
) -> ChatService:
    """Build the same runtime wiring as the API dependency for direct stream tests."""
    selected_registry = registry or create_phase_three_registry()
    executor = ToolExecutor(
        database=database,
        registry=selected_registry,
        timeout_seconds=timeout_seconds or settings.tool_timeout_seconds,
    )
    return ChatService(
        database=database,
        runtime=AgentRuntime(
            model=model,
            registry=selected_registry,
            executor=executor,
            max_loops=settings.max_agent_loops,
        ),
    )


@pytest.mark.anyio
async def test_chat_stream_persists_messages_run_and_title(migrated_settings: Settings) -> None:
    """A direct answer follows the SSE contract and becomes authoritative history."""
    app = create_app(migrated_settings)
    model = RecordingModel("流式回答")
    app.state.model_client = model
    transport = ASGITransport(app=app)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        response = await client.post(
            f"/api/threads/{thread_id}/chat/stream",
            json={"message": "  请解释 Agent Loop  "},
        )
        events = parse_sse(response.text)

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["x-accel-buffering"] == "no"
        assert [event["event"] for event in events] == [
            "run_start",
            "assistant_start",
            "assistant_delta",
            "assistant_delta",
            "assistant_end",
            "run_end",
        ]
        assert all(event["thread_id"] == thread_id for event in events)
        deltas = [
            cast(dict[str, str], event["data"])["content"]
            for event in events
            if event["event"] == "assistant_delta"
        ]
        assert "".join(deltas) == "流式回答"
        assert model.tool_definitions[0][0].name == "get_current_time"

        history = (await client.get(f"/api/threads/{thread_id}/messages")).json()
        assert [(item["role"], item["content"]) for item in history["items"]] == [
            ("user", "请解释 Agent Loop"),
            ("assistant", "流式回答"),
        ]
        thread = (await client.get(f"/api/threads/{thread_id}")).json()
        assert thread["title"] == "请解释 Agent Loop"

        database = cast(Database, app.state.database)
        with database.session_factory() as session:
            run = session.scalar(select(Run).where(Run.thread_id == thread_id))
            assert run is not None
            assert run.status == "success"
            assert run.loop_count == 1


@pytest.mark.anyio
async def test_tool_result_returns_to_model_and_is_persisted(
    migrated_settings: Settings,
) -> None:
    """A successful tool call emits safe status and becomes a ToolMessage."""
    model = ScriptedModel(
        (
            (ModelStreamChunk(tool_calls=(tool_chunk("get_current_time", {"timezone": "UTC"}),)),),
            (ModelStreamChunk(content="当前 UTC 时间已查询完成。"),),
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
            json={"message": "现在几点?"},
        )
        events = parse_sse(response.text)

        assert [event["event"] for event in events] == [
            "run_start",
            "assistant_start",
            "tool_start",
            "tool_result",
            "assistant_delta",
            "assistant_end",
            "run_end",
        ]
        tool_start = cast(dict[str, object], events[2]["data"])
        tool_result = cast(dict[str, object], events[3]["data"])
        assert tool_start["tool_name"] == "get_current_time"
        assert tool_start["display_name"] == "正在查询当前时间"
        assert tool_start["arguments"] == {"timezone": "UTC"}
        assert "iso_time" not in tool_result
        assert tool_result["success"] is True
        assert isinstance(model.contexts[1][-1], ToolMessage)
        tool_message = model.contexts[1][-1]
        assert isinstance(tool_message, ToolMessage)
        assert isinstance(tool_message.content, str)
        returned_payload = json.loads(tool_message.content)
        assert returned_payload["data"]["timezone"] == "UTC"

        database = cast(Database, app.state.database)
        with database.session_factory() as session:
            tool_record = session.scalar(select(ToolCall).where(ToolCall.thread_id == thread_id))
            run = session.scalar(select(Run).where(Run.thread_id == thread_id))
            assert tool_record is not None
            assert tool_record.status == "success"
            assert tool_record.arguments_json == {"timezone": "UTC"}
            assert tool_record.result_json is not None
            assert tool_record.duration_ms is not None
            assert run is not None
            assert run.status == "success"
            assert run.loop_count == 2


@pytest.mark.anyio
async def test_invalid_arguments_can_be_corrected_by_the_model(
    migrated_settings: Settings,
) -> None:
    """Invalid Pydantic arguments are rejected, recorded, and returned for correction."""
    model = ScriptedModel(
        (
            (ModelStreamChunk(tool_calls=(tool_chunk("get_current_time", {"timezone": "Mars"}),)),),
            (
                ModelStreamChunk(
                    tool_calls=(tool_chunk("get_current_time", {"timezone": "+08:00"}),)
                ),
            ),
            (ModelStreamChunk(content="北京时间已查询。"),),
        )
    )
    app = create_app(migrated_settings)
    app.state.model_client = model

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        events = parse_sse(
            (
                await client.post(
                    f"/api/threads/{thread_id}/chat/stream",
                    json={"message": "查询北京时间"},
                )
            ).text
        )
        results = [
            cast(dict[str, object], event["data"])
            for event in events
            if event["event"] == "tool_result"
        ]
        assert [result["status"] for result in results] == ["rejected", "success"]
        assert cast(dict[str, object], results[0]["error"])["code"] == ("TOOL_ARGUMENT_INVALID")
        assert events[-1]["data"] == {"status": "success", "loop_count": 3}

        database = cast(Database, app.state.database)
        with database.session_factory() as session:
            records = list(
                session.scalars(
                    select(ToolCall)
                    .where(ToolCall.thread_id == thread_id)
                    .order_by(ToolCall.started_at, ToolCall.id)
                )
            )
            assert {record.status for record in records} == {"rejected", "success"}
            rejected = next(record for record in records if record.status == "rejected")
            assert rejected.error_message == "工具参数校验失败"


@pytest.mark.anyio
async def test_unknown_tool_is_rejected_and_returned_to_the_model(
    migrated_settings: Settings,
) -> None:
    """A provider-invented tool name cannot bypass the registry."""
    model = ScriptedModel(
        (
            (ModelStreamChunk(tool_calls=(tool_chunk("invented_tool", {"secret": "ignored"}),)),),
            (ModelStreamChunk(content="该工具不可用。"),),
        )
    )
    app = create_app(migrated_settings)
    app.state.model_client = model

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        events = parse_sse(
            (
                await client.post(
                    f"/api/threads/{thread_id}/chat/stream",
                    json={"message": "尝试不存在的工具"},
                )
            ).text
        )
        result = next(
            cast(dict[str, object], event["data"])
            for event in events
            if event["event"] == "tool_result"
        )
        assert result["status"] == "rejected"
        assert cast(dict[str, object], result["error"])["code"] == "TOOL_NOT_FOUND"

        database = cast(Database, app.state.database)
        with database.session_factory() as session:
            record = session.scalar(select(ToolCall).where(ToolCall.thread_id == thread_id))
            assert record is not None
            assert record.status == "rejected"
            assert record.arguments_json == {}


@pytest.mark.anyio
async def test_consecutive_duplicate_tool_call_is_blocked(
    migrated_settings: Settings,
) -> None:
    """The normalized tool name and arguments block an immediate duplicate."""
    duplicate_turn = (
        ModelStreamChunk(tool_calls=(tool_chunk("get_current_time", {"timezone": "UTC"}),)),
    )
    model = ScriptedModel(
        (
            duplicate_turn,
            duplicate_turn,
            (ModelStreamChunk(content="已使用首次查询结果。"),),
        )
    )
    app = create_app(migrated_settings)
    app.state.model_client = model

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        events = parse_sse(
            (
                await client.post(
                    f"/api/threads/{thread_id}/chat/stream",
                    json={"message": "查询一次当前时间"},
                )
            ).text
        )
        results = [
            cast(dict[str, object], event["data"])
            for event in events
            if event["event"] == "tool_result"
        ]
        assert [result["status"] for result in results] == ["success", "rejected"]
        assert cast(dict[str, object], results[1]["error"])["code"] == ("DUPLICATE_TOOL_CALL")


@pytest.mark.anyio
async def test_max_loop_limit_stops_without_fake_assistant(
    migrated_settings: Settings,
) -> None:
    """A tool request at the final model loop is recorded and safely stops the run."""
    limited_settings = migrated_settings.model_copy(update={"max_agent_loops": 2})
    model = ScriptedModel(
        (
            (ModelStreamChunk(tool_calls=(tool_chunk("get_current_time", {"timezone": "UTC"}),)),),
            (
                ModelStreamChunk(
                    tool_calls=(tool_chunk("get_current_time", {"timezone": "+08:00"}),)
                ),
            ),
        )
    )
    app = create_app(limited_settings)
    app.state.model_client = model

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        response = await client.post(
            f"/api/threads/{thread_id}/chat/stream",
            json={"message": "持续调用工具"},
        )
        events = parse_sse(response.text)
        assert "assistant_end" not in [event["event"] for event in events]
        assert events[-2]["event"] == "error"
        assert cast(dict[str, object], events[-2]["data"])["code"] == ("MAX_AGENT_LOOPS_REACHED")
        assert events[-1]["data"] == {
            "status": "max_loops_reached",
            "loop_count": 2,
        }
        history = (await client.get(f"/api/threads/{thread_id}/messages")).json()
        assert [(item["role"], item["content"]) for item in history["items"]] == [
            ("user", "持续调用工具")
        ]

        database = cast(Database, app.state.database)
        with database.session_factory() as session:
            run = session.scalar(select(Run).where(Run.thread_id == thread_id))
            records = list(session.scalars(select(ToolCall).where(ToolCall.thread_id == thread_id)))
            assert run is not None
            assert run.status == "max_loops_reached"
            assert run.error_code == "MAX_AGENT_LOOPS_REACHED"
            assert {record.status for record in records} == {"success", "rejected"}


class EmptyArguments(BaseModel):
    """No-argument schema for executor failure-path tools."""

    model_config = ConfigDict(extra="forbid")


async def slow_handler(context: ToolContext, arguments: BaseModel) -> ToolOutput:
    """Sleep long enough for the configured executor timeout."""
    assert isinstance(arguments, EmptyArguments)
    await asyncio.sleep(0.05)
    return ToolOutput(summary="不应完成", data={})


async def broken_handler(context: ToolContext, arguments: BaseModel) -> ToolOutput:
    """Raise an internal error that must be converted to a safe tool result."""
    assert isinstance(arguments, EmptyArguments)
    raise RuntimeError("internal tool detail")


@pytest.mark.anyio
async def test_multiple_tools_run_sequentially_and_failures_do_not_crash(
    migrated_settings: Settings,
) -> None:
    """Timeout and exception results are ordered, persisted, and returned to the model."""
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="slow_tool",
            description="Slow test tool",
            display_name="正在分析问题",
            arguments_schema=EmptyArguments,
            handler=slow_handler,
            public_argument_names=(),
        )
    )
    registry.register(
        Tool(
            name="broken_tool",
            description="Broken test tool",
            display_name="正在分析问题",
            arguments_schema=EmptyArguments,
            handler=broken_handler,
            public_argument_names=(),
        )
    )
    model = ScriptedModel(
        (
            (
                ModelStreamChunk(
                    tool_calls=(
                        tool_chunk("slow_tool", {}, index=0),
                        tool_chunk("broken_tool", {}, index=1),
                    )
                ),
            ),
            (ModelStreamChunk(content="两个工具都失败。已停止依赖它们。"),),
        )
    )
    app = create_app(migrated_settings)
    database = cast(Database, app.state.database)
    service = make_service(
        database=database,
        settings=migrated_settings,
        model=model,
        registry=registry,
        timeout_seconds=0.005,
    )

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        prepared = service.prepare(
            thread_id=thread_id,
            request=ChatRequest(message="顺序执行两个测试工具"),
        )
        events = parse_sse("".join([frame async for frame in service.stream(prepared)]))

    tool_events = [
        (
            event["event"],
            cast(dict[str, object], event["data"])["tool_name"],
            cast(dict[str, object], event["data"]).get("status"),
        )
        for event in events
        if event["event"] in {"tool_start", "tool_result"}
    ]
    assert tool_events == [
        ("tool_start", "slow_tool", None),
        ("tool_result", "slow_tool", "timeout"),
        ("tool_start", "broken_tool", None),
        ("tool_result", "broken_tool", "failed"),
    ]
    assert events[-1]["data"] == {"status": "success", "loop_count": 2}
    with database.session_factory() as session:
        statuses = {
            record.tool_name: record.status
            for record in session.scalars(
                select(ToolCall).where(ToolCall.thread_id == prepared.thread_id)
            )
        }
        assert statuses == {"slow_tool": "timeout", "broken_tool": "failed"}


@pytest.mark.anyio
async def test_twenty_round_context_and_thread_isolation(migrated_settings: Settings) -> None:
    """At least 20 rounds remain ordered and never enter another thread's context."""
    app = create_app(migrated_settings)
    model = RecordingModel("收到")
    app.state.model_client = model

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        first_id = (await client.post("/api/threads")).json()["id"]
        for round_number in range(1, 21):
            response = await client.post(
                f"/api/threads/{first_id}/chat/stream",
                json={"message": f"第 {round_number} 轮"},
            )
            assert response.status_code == 200

        history = (
            await client.get(
                f"/api/threads/{first_id}/messages",
                params={"page_size": 100},
            )
        ).json()
        assert history["total"] == 40
        assert len(model.contexts[-1]) == 39
        assert model.contexts[-1][0].content == "第 1 轮"
        assert model.contexts[-1][-1].content == "第 20 轮"

        second_id = (await client.post("/api/threads")).json()["id"]
        await client.post(
            f"/api/threads/{second_id}/chat/stream",
            json={"message": "独立会话"},
        )
        assert len(model.contexts[-1]) == 1
        assert isinstance(model.contexts[-1][0], HumanMessage)
        assert model.contexts[-1][0].content == "独立会话"


@pytest.mark.anyio
async def test_model_failure_keeps_user_message_without_fake_assistant(
    migrated_settings: Settings,
) -> None:
    """Provider failure emits a safe terminal sequence and persists a failed run."""
    app = create_app(migrated_settings)
    app.state.model_client = FailingModel()

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        response = await client.post(
            f"/api/threads/{thread_id}/chat/stream",
            json={"message": "这条用户消息必须保留"},
        )
        events = parse_sse(response.text)
        assert [event["event"] for event in events] == [
            "run_start",
            "assistant_start",
            "error",
            "run_end",
        ]
        assert cast(dict[str, object], events[-2]["data"])["code"] == ("MODEL_REQUEST_FAILED")

        history = (await client.get(f"/api/threads/{thread_id}/messages")).json()
        assert [(item["role"], item["content"]) for item in history["items"]] == [
            ("user", "这条用户消息必须保留")
        ]
        database = cast(Database, app.state.database)
        with database.session_factory() as session:
            run = session.scalar(select(Run).where(Run.thread_id == thread_id))
            assert run is not None
            assert run.status == "failed"
            assert run.loop_count == 1
            assert run.assistant_message_id is None


@pytest.mark.anyio
async def test_chat_preflight_errors_are_json_and_do_not_create_runs(
    migrated_settings: Settings,
) -> None:
    """Empty, missing, file, and busy requests fail before an SSE response starts."""
    app = create_app(migrated_settings)
    model = RecordingModel()
    app.state.model_client = model

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        missing = await client.post(
            "/api/threads/not-found/chat/stream",
            json={"message": "hello"},
        )
        thread_id = (await client.post("/api/threads")).json()["id"]
        empty = await client.post(
            f"/api/threads/{thread_id}/chat/stream",
            json={"message": "  \n "},
        )
        file_request = await client.post(
            f"/api/threads/{thread_id}/chat/stream",
            json={"message": "读取文件", "file_ids": ["unknown"]},
        )

        database = cast(Database, app.state.database)
        service = make_service(
            database=database,
            settings=migrated_settings,
            model=model,
        )
        prepared = service.prepare(
            thread_id=thread_id,
            request=ChatRequest(message="正在运行"),
        )
        busy = await client.post(
            f"/api/threads/{thread_id}/chat/stream",
            json={"message": "第二个任务"},
        )
        _ = [frame async for frame in service.stream(prepared)]

    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "THREAD_NOT_FOUND"
    assert empty.status_code == 400
    assert empty.json()["error"]["code"] == "MESSAGE_EMPTY"
    assert file_request.status_code == 404
    assert file_request.json()["error"]["code"] == "FILE_NOT_FOUND"
    assert busy.status_code == 409
    assert busy.json()["error"]["code"] == "THREAD_BUSY"


@pytest.mark.anyio
async def test_stream_close_marks_run_cancelled(migrated_settings: Settings) -> None:
    """Closing an SSE iterator after its first frame releases the active run."""
    app = create_app(migrated_settings)
    model = RecordingModel()
    app.state.model_client = model
    database = cast(Database, app.state.database)
    service = make_service(
        database=database,
        settings=migrated_settings,
        model=model,
    )
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        prepared = service.prepare(
            thread_id=thread_id,
            request=ChatRequest(message="连接即将断开"),
        )
        stream = service.stream(prepared)
        first_frame = await anext(stream)
        assert '"event":"run_start"' in first_frame
        await stream.aclose()

        with database.session_factory() as session:
            run = session.get(Run, prepared.run_id)
            assert run is not None
            assert run.status == "cancelled"
            assert run.finished_at is not None

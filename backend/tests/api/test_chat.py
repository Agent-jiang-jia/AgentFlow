"""Plain streaming chat API and persistence tests."""

import json
from collections.abc import AsyncIterator, Sequence
from typing import cast

import pytest
from app.core.config import Settings
from app.db.database import Database
from app.db.models.run import Run
from app.main import create_app
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.model_client import ModelClientError, ModelMessage
from httpx import ASGITransport, AsyncClient
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


class RecordingModel:
    """Deterministic streaming model that records every received context."""

    def __init__(self, response: str = "你好世界") -> None:
        self.response = response
        self.contexts: list[tuple[ModelMessage, ...]] = []

    async def stream(self, messages: Sequence[ModelMessage]) -> AsyncIterator[str]:
        self.contexts.append(tuple(messages))
        midpoint = max(1, len(self.response) // 2)
        yield self.response[:midpoint]
        yield self.response[midpoint:]


class FailingModel:
    """Model double that fails before producing a content delta."""

    async def stream(self, messages: Sequence[ModelMessage]) -> AsyncIterator[str]:
        assert messages
        if False:
            yield ""
        raise ModelClientError("provider unavailable")


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

        history = (await client.get(f"/api/threads/{thread_id}/messages")).json()
        assert [(item["role"], item["content"]) for item in history["items"]] == [
            ("user", "请解释 Agent Loop"),
            ("assistant", "流式回答"),
        ]
        assert [item["sequence_number"] for item in history["items"]] == [1, 2]
        thread = (await client.get(f"/api/threads/{thread_id}")).json()
        assert thread["title"] == "请解释 Agent Loop"

        database = cast(Database, app.state.database)
        with database.session_factory() as session:
            run = session.scalar(select(Run).where(Run.thread_id == thread_id))
            assert run is not None
            assert run.status == "success"
            assert run.loop_count == 1
            assert run.user_message_id == history["items"][0]["id"]
            assert run.assistant_message_id == history["items"][1]["id"]


@pytest.mark.anyio
async def test_twenty_round_context_and_thread_isolation(migrated_settings: Settings) -> None:
    """At least 20 rounds remain ordered and never enter another thread's context."""
    app = create_app(migrated_settings)
    model = RecordingModel("收到")
    app.state.model_client = model
    transport = ASGITransport(app=app)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        first_id = (await client.post("/api/threads")).json()["id"]
        for round_number in range(1, 21):
            response = await client.post(
                f"/api/threads/{first_id}/chat/stream",
                json={"message": f"第 {round_number} 轮"},
            )
            assert response.status_code == 200
            assert parse_sse(response.text)[-1]["data"] == {
                "status": "success",
                "loop_count": 1,
            }

        history = (
            await client.get(
                f"/api/threads/{first_id}/messages",
                params={"page_size": 100},
            )
        ).json()
        assert history["total"] == 40
        assert [item["sequence_number"] for item in history["items"]] == list(range(1, 41))
        assert len(model.contexts[-1]) == 39
        assert model.contexts[-1][0].content == "第 1 轮"
        assert model.contexts[-1][-1].content == "第 20 轮"

        second_id = (await client.post("/api/threads")).json()["id"]
        await client.post(
            f"/api/threads/{second_id}/chat/stream",
            json={"message": "独立会话"},
        )
        assert [(item.role, item.content) for item in model.contexts[-1]] == [("user", "独立会话")]


@pytest.mark.anyio
async def test_model_failure_keeps_user_message_without_fake_assistant(
    migrated_settings: Settings,
) -> None:
    """Provider failure emits a safe terminal sequence and persists a failed run."""
    app = create_app(migrated_settings)
    app.state.model_client = FailingModel()
    transport = ASGITransport(app=app)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
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
        assert events[-2]["data"] == {
            "code": "MODEL_REQUEST_FAILED",
            "message": "模型服务暂时不可用",
            "retryable": True,
            "details": {},
        }

        history = (await client.get(f"/api/threads/{thread_id}/messages")).json()
        assert [(item["role"], item["content"]) for item in history["items"]] == [
            ("user", "这条用户消息必须保留")
        ]
        database = cast(Database, app.state.database)
        with database.session_factory() as session:
            run = session.scalar(select(Run).where(Run.thread_id == thread_id))
            assert run is not None
            assert run.status == "failed"
            assert run.error_code == "MODEL_REQUEST_FAILED"
            assert run.assistant_message_id is None


@pytest.mark.anyio
async def test_chat_preflight_errors_are_json_and_do_not_create_runs(
    migrated_settings: Settings,
) -> None:
    """Empty, missing, file, and busy requests fail before an SSE response starts."""
    app = create_app(migrated_settings)
    model = RecordingModel()
    app.state.model_client = model
    transport = ASGITransport(app=app)

    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
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
        service = ChatService(database=database, model=model)
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
    service = ChatService(database=database, model=model)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        thread_service_response = await client.post("/api/threads")
        thread_id = thread_service_response.json()["id"]
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

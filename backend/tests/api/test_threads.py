"""Thread CRUD API tests."""

from collections.abc import AsyncIterator, Sequence
from typing import cast

import pytest
from app.agent.runtime import AgentRuntime
from app.core.config import Settings
from app.db.database import Database
from app.db.models.message import Message
from app.db.models.run import Run
from app.db.models.thread import Thread
from app.main import create_app
from app.schemas.chat import ChatRequest
from app.services.chat_service import ChatService
from app.services.model_client import ModelStreamChunk
from app.tools import create_phase_three_registry
from app.tools.base import ToolDefinition
from app.tools.executor import ToolExecutor
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import BaseMessage
from sqlalchemy import func, select


class StaticModel:
    """Small deterministic model used to create persisted chat state."""

    async def stream(
        self,
        messages: Sequence[BaseMessage],
        tools: Sequence[ToolDefinition],
    ) -> AsyncIterator[ModelStreamChunk]:
        assert messages
        assert tools
        yield ModelStreamChunk(content="已记录")


@pytest.mark.anyio
async def test_thread_crud_creates_sorts_and_removes_directories(
    migrated_settings: Settings,
) -> None:
    """CRUD uses the specified response shapes and controlled thread tree."""
    app = create_app(migrated_settings)
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        first_response = await client.post("/api/threads", json={"title": "  第一会话  "})
        second_response = await client.post("/api/threads")

        assert first_response.status_code == 201
        assert first_response.json()["title"] == "第一会话"
        assert first_response.json()["created_at"].endswith("Z")
        first_id = first_response.json()["id"]
        second_id = second_response.json()["id"]

        for thread_id in (first_id, second_id):
            thread_root = migrated_settings.resolved_data_dir / "threads" / thread_id
            assert {path.name for path in thread_root.iterdir()} == {
                "uploads",
                "parsed",
                "outputs",
            }

        listing = await client.get("/api/threads", params={"page": 1, "page_size": 1})
        assert listing.status_code == 200
        assert listing.json()["total"] == 2
        assert listing.json()["items"][0]["id"] == second_id

        detail = await client.get(f"/api/threads/{first_id}")
        assert detail.status_code == 200
        assert detail.json()["title"] == "第一会话"

        messages = await client.get(f"/api/threads/{first_id}/messages")
        assert messages.json() == {"items": [], "page": 1, "page_size": 20, "total": 0}

        deleted = await client.delete(f"/api/threads/{first_id}")
        assert deleted.status_code == 204
        assert not (migrated_settings.resolved_data_dir / "threads" / first_id).exists()
        assert (await client.get(f"/api/threads/{first_id}")).status_code == 404

        missing = await client.delete("/api/threads/not-a-thread")
        assert missing.status_code == 404
        assert missing.json()["error"]["code"] == "THREAD_NOT_FOUND"


@pytest.mark.anyio
async def test_delete_rejects_active_run_and_then_cascades_chat_records(
    migrated_settings: Settings,
) -> None:
    """Active work blocks deletion; completed run and messages cascade with the thread."""
    app = create_app(migrated_settings)
    app.state.model_client = StaticModel()
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        thread_id = (await client.post("/api/threads")).json()["id"]
        database = cast(Database, app.state.database)
        registry = create_phase_three_registry()
        service = ChatService(
            database=database,
            runtime=AgentRuntime(
                model=cast(StaticModel, app.state.model_client),
                registry=registry,
                executor=ToolExecutor(
                    database=database,
                    registry=registry,
                    timeout_seconds=migrated_settings.tool_timeout_seconds,
                ),
                max_loops=migrated_settings.max_agent_loops,
            ),
        )
        prepared = service.prepare(
            thread_id=thread_id,
            request=ChatRequest(message="保留这条消息"),
        )

        busy = await client.delete(f"/api/threads/{thread_id}")
        assert busy.status_code == 409
        assert busy.json()["error"]["code"] == "THREAD_BUSY"

        frames = [frame async for frame in service.stream(prepared)]
        assert any('"status":"success"' in frame for frame in frames)
        deleted = await client.delete(f"/api/threads/{thread_id}")
        assert deleted.status_code == 204

        with database.session_factory() as session:
            assert session.scalar(select(func.count()).select_from(Thread)) == 0
            assert session.scalar(select(func.count()).select_from(Message)) == 0
            assert session.scalar(select(func.count()).select_from(Run)) == 0


@pytest.mark.anyio
async def test_thread_input_validation_is_safe(migrated_settings: Settings) -> None:
    """Invalid pagination and blank titles use the common validation envelope."""
    app = create_app(migrated_settings)
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        blank = await client.post("/api/threads", json={"title": "   "})
        invalid_page = await client.get("/api/threads", params={"page": 0})

    assert blank.status_code == 422
    assert blank.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"
    assert "   " not in blank.text
    assert invalid_page.status_code == 422

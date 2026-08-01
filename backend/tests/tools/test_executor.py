"""Tool executor cancellation consistency tests."""

import asyncio
from uuid import uuid4

import pytest
from app.core.config import Settings
from app.db.database import Database
from app.db.models.run import Run
from app.db.models.thread import Thread, utc_now
from app.db.models.tool_call import ToolCall
from app.tools.base import Tool, ToolContext, ToolOutput
from app.tools.executor import ToolExecutor
from app.tools.registry import ToolRegistry
from pydantic import BaseModel, ConfigDict


class NoArguments(BaseModel):
    """Strict empty argument schema for the cancellable test tool."""

    model_config = ConfigDict(extra="forbid")


@pytest.mark.anyio
async def test_cancelled_tool_execution_is_persisted_as_failed(
    migrated_settings: Settings,
) -> None:
    """Client disconnect cancellation cannot leave a tool call permanently running."""
    database = Database(migrated_settings.resolved_database_path)
    thread_id = str(uuid4())
    run_id = str(uuid4())
    timestamp = utc_now()
    with database.session_factory() as session:
        session.add(
            Thread(
                id=thread_id,
                title="cancel",
                status="active",
                created_at=timestamp,
                updated_at=timestamp,
            )
        )
        session.flush()
        session.add(
            Run(
                id=run_id,
                thread_id=thread_id,
                status="running",
                user_message_id=None,
                assistant_message_id=None,
                loop_count=1,
                error_code=None,
                error_message=None,
                started_at=timestamp,
                finished_at=None,
            )
        )
        session.commit()

    blocker = asyncio.Event()

    async def wait_forever(_context: ToolContext, _arguments: BaseModel) -> ToolOutput:
        await blocker.wait()
        return ToolOutput(summary="unexpected", data={})

    registry = ToolRegistry()
    registry.register(
        Tool(
            name="wait_forever",
            description="Wait until cancelled.",
            display_name="正在分析问题",
            arguments_schema=NoArguments,
            handler=wait_forever,
            public_argument_names=(),
        )
    )
    executor = ToolExecutor(database=database, registry=registry, timeout_seconds=30)
    invocation = executor.prepare(
        context=ToolContext(thread_id=thread_id, run_id=run_id),
        tool_call_id="cancelled-tool",
        tool_name="wait_forever",
        raw_arguments={},
        previous_signature=None,
    )
    task = asyncio.create_task(executor.execute(invocation))
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    with database.session_factory() as session:
        record = session.get(ToolCall, "cancelled-tool")
        assert record is not None
        assert record.status == "failed"
        assert record.finished_at is not None
        assert record.duration_ms is not None
        assert record.error_message == "工具执行已取消"
        assert record.result_json is not None
        assert record.result_json["error"]["code"] == "TOOL_EXECUTION_FAILED"
    database.dispose()

"""Process-restart recovery and cross-resource compensation tests."""

from typing import cast
from uuid import uuid4

import pytest
from app.core.config import Settings
from app.db.database import Database
from app.db.models.file import File
from app.db.models.run import Run
from app.db.models.thread import Thread, utc_now
from app.db.models.tool_call import ToolCall
from app.main import create_app
from app.services.recovery_service import RecoveryReport
from app.storage.file_storage import FileStorage
from app.storage.thread_storage import ThreadStorage
from httpx import ASGITransport, AsyncClient


@pytest.mark.anyio
async def test_startup_recovers_interrupted_runs_and_storage(
    migrated_settings: Settings,
) -> None:
    """Restart releases locks and resolves both sides of staged delete transactions."""
    database = Database(migrated_settings.resolved_database_path)
    thread_storage = ThreadStorage(migrated_settings.resolved_data_dir)
    file_storage = FileStorage(migrated_settings.resolved_data_dir)
    active_thread_id = str(uuid4())
    staged_thread_id = str(uuid4())
    orphan_thread_id = str(uuid4())
    run_id = str(uuid4())
    file_id = str(uuid4())
    timestamp = utc_now()

    active_root = thread_storage.create(active_thread_id)
    _ = thread_storage.create(staged_thread_id)
    _ = thread_storage.create(orphan_thread_id)
    stored_path = f"threads/{active_thread_id}/uploads/{file_id}_notes.txt"
    original_file = active_root / "uploads" / f"{file_id}_notes.txt"
    original_file.write_text("recoverable", encoding="utf-8")
    orphan_file = active_root / "outputs" / f"{uuid4()}_orphan.md"
    orphan_file.write_text("orphan", encoding="utf-8")

    with database.session_factory() as session:
        session.add_all(
            [
                Thread(
                    id=active_thread_id,
                    title="active",
                    status="active",
                    created_at=timestamp,
                    updated_at=timestamp,
                ),
                Thread(
                    id=staged_thread_id,
                    title="staged",
                    status="active",
                    created_at=timestamp,
                    updated_at=timestamp,
                ),
            ]
        )
        session.flush()
        session.add(
            Run(
                id=run_id,
                thread_id=active_thread_id,
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
        session.flush()
        session.add_all(
            [
                ToolCall(
                    id="interrupted-tool",
                    run_id=run_id,
                    thread_id=active_thread_id,
                    tool_name="read_file",
                    arguments_json={"file_id": file_id},
                    result_json=None,
                    status="running",
                    error_message=None,
                    duration_ms=None,
                    started_at=timestamp,
                    finished_at=None,
                ),
                File(
                    id=file_id,
                    thread_id=active_thread_id,
                    source_file_id=None,
                    category="upload",
                    original_name="notes.txt",
                    stored_name=original_file.name,
                    stored_path=stored_path,
                    extension=".txt",
                    mime_type="text/plain",
                    size_bytes=len("recoverable"),
                    parse_status="failed",
                    parse_error="文件解析失败",
                    description=None,
                    created_at=timestamp,
                ),
            ]
        )
        session.commit()

    staged_files = file_storage.stage_delete(
        thread_id=active_thread_id,
        stored_paths=(stored_path,),
    )
    staged_thread = thread_storage.stage_delete(staged_thread_id)
    assert staged_files and staged_thread is not None
    assert not original_file.exists()
    database.dispose()

    app = create_app(migrated_settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        report = cast(RecoveryReport, app.state.recovery_report)
        assert report.schema_ready is True
        assert report.cancelled_runs == 1
        assert report.failed_tool_calls == 1
        assert report.thread_storage.restored == 1
        assert report.thread_storage.purged == 1
        assert report.file_storage.restored == 1
        assert report.file_storage.purged == 1
        assert original_file.read_text(encoding="utf-8") == "recoverable"
        assert (migrated_settings.resolved_data_dir / "threads" / staged_thread_id).is_dir()
        assert not (migrated_settings.resolved_data_dir / "threads" / orphan_thread_id).exists()
        assert not orphan_file.exists()

        response = await client.post(
            f"/api/threads/{active_thread_id}/chat/stream",
            json={"message": "restart released the run lock"},
        )
        assert response.status_code == 200
        assert '"status":"failed"' in response.text

        current_database = cast(Database, app.state.database)
        with current_database.session_factory() as session:
            interrupted_run = session.get(Run, run_id)
            interrupted_tool = session.get(ToolCall, "interrupted-tool")
            assert interrupted_run is not None
            assert interrupted_run.status == "cancelled"
            assert interrupted_run.finished_at is not None
            assert interrupted_tool is not None
            assert interrupted_tool.status == "failed"
            assert interrupted_tool.finished_at is not None
            assert interrupted_tool.duration_ms is not None
            assert interrupted_tool.result_json is not None
            assert interrupted_tool.result_json["error"]["code"] == "TOOL_EXECUTION_FAILED"

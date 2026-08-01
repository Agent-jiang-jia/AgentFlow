"""Startup recovery for interrupted runs and cross-resource file operations."""

from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import inspect, text

from app.core.error_codes import ErrorCode
from app.db.database import Database
from app.db.models.thread import utc_now
from app.db.repositories.file_repository import FileRepository
from app.db.repositories.run_repository import RunRepository
from app.db.repositories.thread_repository import ThreadRepository
from app.db.repositories.tool_call_repository import ToolCallRepository
from app.storage.file_storage import FileRecoveryResult, FileStorage
from app.storage.thread_storage import ThreadRecoveryResult, ThreadStorage

_REQUIRED_TABLES = frozenset({"threads", "runs", "tool_calls", "files"})


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    """Non-sensitive startup recovery counts suitable for structured logs."""

    schema_ready: bool
    cancelled_runs: int = 0
    failed_tool_calls: int = 0
    thread_storage: ThreadRecoveryResult = field(default_factory=ThreadRecoveryResult)
    file_storage: FileRecoveryResult = field(default_factory=FileRecoveryResult)


class RecoveryService:
    """Reconcile terminal database state with controlled local storage."""

    def __init__(
        self,
        *,
        database: Database,
        thread_storage: ThreadStorage,
        file_storage: FileStorage,
    ) -> None:
        self._database = database
        self._thread_storage = thread_storage
        self._file_storage = file_storage

    def recover(self) -> RecoveryReport:
        """Recover work interrupted by a previous process without creating schema."""
        table_names = set(inspect(self._database.engine).get_table_names())
        if not _REQUIRED_TABLES.issubset(table_names):
            return RecoveryReport(schema_ready=False)

        timestamp = utc_now()
        with self._database.session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            active_tool_calls = ToolCallRepository(session).list_active()
            for tool_call in active_tool_calls:
                tool_call.status = "failed"
                tool_call.result_json = {
                    "success": False,
                    "status": "failed",
                    "summary": "服务重启后工具执行已终止",
                    "data": {},
                    "error": {
                        "code": ErrorCode.TOOL_EXECUTION_FAILED.value,
                        "message": "服务重启后工具执行已终止",
                        "retryable": True,
                    },
                }
                tool_call.error_message = "服务重启后工具执行已终止"
                tool_call.duration_ms = self._duration_ms(tool_call.started_at, timestamp)
                tool_call.finished_at = timestamp

            active_runs = RunRepository(session).list_active()
            for run in active_runs:
                run.status = "cancelled"
                run.error_code = None
                run.error_message = "服务重启后任务已取消"
                run.finished_at = timestamp

            thread_ids = ThreadRepository(session).list_ids()
            stored_paths = FileRepository(session).list_stored_paths()
            session.commit()

        thread_result = self._thread_storage.recover(thread_ids)
        file_result = self._file_storage.recover(stored_paths)
        return RecoveryReport(
            schema_ready=True,
            cancelled_runs=len(active_runs),
            failed_tool_calls=len(active_tool_calls),
            thread_storage=thread_result,
            file_storage=file_result,
        )

    @staticmethod
    def _duration_ms(started_at: datetime, finished_at: datetime) -> int:
        start = started_at
        finish = finished_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if finish.tzinfo is None:
            finish = finish.replace(tzinfo=UTC)
        return max(0, round((finish - start).total_seconds() * 1000))

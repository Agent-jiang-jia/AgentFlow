"""Sequential, persisted tool execution with safety guards."""

import asyncio
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from time import perf_counter

from pydantic import BaseModel, ValidationError

from app.core.error_codes import ErrorCode
from app.db.database import Database
from app.db.models.thread import utc_now
from app.db.models.tool_call import ToolCall
from app.db.repositories.tool_call_repository import ToolCallRepository
from app.tools.base import Tool, ToolContext, ToolError, ToolFailure, ToolOutput
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PreparedToolInvocation:
    """Validated and persisted state before a tool handler starts."""

    context: ToolContext
    tool_call_id: str
    tool_name: str
    public_arguments: dict[str, object]
    signature: str
    tool: Tool | None
    validated_arguments: BaseModel | None
    rejection: ToolError | None


@dataclass(frozen=True, slots=True)
class ToolExecution:
    """Terminal tool result used by SSE, persistence, and ToolMessage."""

    tool_call_id: str
    tool_name: str
    success: bool
    status: str
    summary: str
    data: dict[str, object]
    error: ToolError | None

    def model_payload(self) -> dict[str, object]:
        """Return structured content for the model-facing ToolMessage."""
        return {
            "success": self.success,
            "status": self.status,
            "summary": self.summary,
            "data": self.data,
            "error": None if self.error is None else self.error.as_dict(),
        }


class ToolExecutor:
    """Validate, deduplicate, time-limit, and persist one tool at a time."""

    def __init__(
        self,
        *,
        database: Database,
        registry: ToolRegistry,
        timeout_seconds: float,
    ) -> None:
        self._database = database
        self._registry = registry
        self._timeout_seconds = timeout_seconds

    def prepare(
        self,
        *,
        context: ToolContext,
        tool_call_id: str,
        tool_name: str,
        raw_arguments: object,
        previous_signature: str | None,
        forced_rejection: ToolError | None = None,
    ) -> PreparedToolInvocation:
        """Validate and record a running or rejected invocation."""
        tool = self._registry.get(tool_name)
        validated: BaseModel | None = None
        public_arguments: dict[str, object] = {}
        rejection = forced_rejection

        if tool is None:
            rejection = rejection or ToolError(
                code=ErrorCode.TOOL_NOT_FOUND,
                message="工具不存在",
            )
        elif not isinstance(raw_arguments, Mapping):
            rejection = rejection or ToolError(
                code=ErrorCode.TOOL_ARGUMENT_INVALID,
                message="工具参数校验失败",
            )
        else:
            raw_mapping = {
                str(key): value for key, value in raw_arguments.items() if isinstance(key, str)
            }
            public_arguments = tool.safe_arguments(raw_mapping)
            try:
                validated = tool.arguments_schema.model_validate(raw_mapping)
            except ValidationError:
                rejection = rejection or ToolError(
                    code=ErrorCode.TOOL_ARGUMENT_INVALID,
                    message="工具参数校验失败",
                )
            else:
                normalized = validated.model_dump(mode="json")
                public_arguments = tool.safe_arguments(normalized)

        signature_arguments = (
            validated.model_dump(mode="json") if validated is not None else public_arguments
        )
        signature = self._signature(tool_name, signature_arguments)
        if rejection is None and signature == previous_signature:
            rejection = ToolError(
                code=ErrorCode.DUPLICATE_TOOL_CALL,
                message="检测到重复工具调用",
            )

        timestamp = utc_now()
        terminal = rejection is not None
        with self._database.session_factory() as session:
            ToolCallRepository(session).add(
                ToolCall(
                    id=tool_call_id,
                    run_id=context.run_id,
                    thread_id=context.thread_id,
                    tool_name=tool_name[:100],
                    arguments_json=public_arguments,
                    result_json=(
                        self._error_result(rejection).model_payload()
                        if rejection is not None
                        else None
                    ),
                    status="rejected" if terminal else "running",
                    error_message=rejection.message if rejection is not None else None,
                    duration_ms=0 if terminal else None,
                    started_at=timestamp,
                    finished_at=timestamp if terminal else None,
                )
            )
            session.commit()

        return PreparedToolInvocation(
            context=context,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            public_arguments=public_arguments,
            signature=signature,
            tool=tool,
            validated_arguments=validated,
            rejection=rejection,
        )

    async def execute(self, invocation: PreparedToolInvocation) -> ToolExecution:
        """Execute a prepared handler, converting all failures to safe results."""
        if invocation.rejection is not None:
            return self._error_result(
                invocation.rejection,
                tool_call_id=invocation.tool_call_id,
                tool_name=invocation.tool_name,
            )
        if invocation.tool is None or invocation.validated_arguments is None:
            raise RuntimeError("Prepared tool invocation lost validated state")

        started = perf_counter()
        try:
            async with asyncio.timeout(self._timeout_seconds):
                output = await invocation.tool.execute(
                    invocation.context,
                    invocation.validated_arguments,
                )
            self._ensure_json_serializable(output)
        except TimeoutError:
            execution = self._error_result(
                ToolError(
                    code=ErrorCode.TOOL_TIMEOUT,
                    message="工具执行超时",
                    retryable=True,
                ),
                status="timeout",
                tool_call_id=invocation.tool_call_id,
                tool_name=invocation.tool_name,
            )
        except ToolFailure as exc:
            execution = self._error_result(
                exc.error,
                status="failed",
                tool_call_id=invocation.tool_call_id,
                tool_name=invocation.tool_name,
            )
        except Exception:
            logger.exception(
                "Tool execution failed",
                extra={
                    "thread_id": invocation.context.thread_id,
                    "run_id": invocation.context.run_id,
                    "tool_call_id": invocation.tool_call_id,
                    "tool_name": invocation.tool_name,
                },
            )
            execution = self._error_result(
                ToolError(
                    code=ErrorCode.TOOL_EXECUTION_FAILED,
                    message="工具执行失败",
                ),
                status="failed",
                tool_call_id=invocation.tool_call_id,
                tool_name=invocation.tool_name,
            )
        else:
            execution = ToolExecution(
                tool_call_id=invocation.tool_call_id,
                tool_name=invocation.tool_name,
                success=True,
                status="success",
                summary=output.summary[:500],
                data=output.data,
                error=None,
            )

        duration_ms = max(0, round((perf_counter() - started) * 1000))
        self._finish(invocation, execution, duration_ms)
        return execution

    def reject(
        self,
        *,
        context: ToolContext,
        tool_call_id: str,
        tool_name: str,
        raw_arguments: object,
        error: ToolError,
    ) -> PreparedToolInvocation:
        """Persist a policy-rejected call without executing its handler."""
        return self.prepare(
            context=context,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            raw_arguments=raw_arguments,
            previous_signature=None,
            forced_rejection=error,
        )

    def display_name(self, tool_name: str) -> str:
        """Return the registry's allow-listed public status label."""
        return self._registry.display_name(tool_name)

    def stream_arguments(
        self,
        tool_name: str,
        arguments: Mapping[str, object],
    ) -> dict[str, object]:
        """Return only arguments approved for the public tool-start event."""
        tool = self._registry.get(tool_name)
        return tool.stream_arguments(arguments) if tool is not None else {}

    @staticmethod
    def _signature(tool_name: str, arguments: Mapping[str, object]) -> str:
        serialized = json.dumps(
            arguments,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"{tool_name}:{serialized}"

    @staticmethod
    def _ensure_json_serializable(output: ToolOutput) -> None:
        json.dumps(output.data, ensure_ascii=False, allow_nan=False)

    @staticmethod
    def _error_result(
        error: ToolError,
        *,
        status: str = "rejected",
        tool_call_id: str = "",
        tool_name: str = "",
    ) -> ToolExecution:
        return ToolExecution(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            success=False,
            status=status,
            summary=error.message,
            data={},
            error=error,
        )

    def _finish(
        self,
        invocation: PreparedToolInvocation,
        execution: ToolExecution,
        duration_ms: int,
    ) -> None:
        with self._database.session_factory() as session:
            record = ToolCallRepository(session).get_for_run(
                tool_call_id=invocation.tool_call_id,
                run_id=invocation.context.run_id,
                thread_id=invocation.context.thread_id,
            )
            if record is None or record.status != "running":
                raise RuntimeError("Running tool-call state was lost")
            record.status = execution.status
            record.result_json = execution.model_payload()
            record.error_message = execution.error.message if execution.error is not None else None
            record.duration_ms = duration_ms
            record.finished_at = utc_now()
            session.commit()

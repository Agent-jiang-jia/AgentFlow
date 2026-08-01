"""Plain Phase 2 streaming chat orchestration."""

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, MessageEmptyError, ThreadBusyError, ThreadNotFoundError
from app.db.database import Database
from app.db.models.message import Message
from app.db.models.run import Run
from app.db.models.thread import utc_now
from app.db.repositories.message_repository import MessageRepository
from app.db.repositories.run_repository import RunRepository
from app.db.repositories.thread_repository import ThreadRepository
from app.schemas.chat import ChatRequest, SseEvent, SseEventName
from app.services.model_client import ChatModel, ModelClientError, ModelMessage

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PreparedChat:
    """Persisted pre-stream state for one chat run."""

    thread_id: str
    run_id: str
    assistant_message_id: str
    context: tuple[ModelMessage, ...]


class ChatService:
    """Persist and stream a direct model answer without Phase 3 tools."""

    def __init__(self, *, database: Database, model: ChatModel) -> None:
        self._database = database
        self._model = model

    def prepare(self, *, thread_id: str, request: ChatRequest) -> PreparedChat:
        """Validate and persist the user message before the SSE response starts."""
        content = request.message.strip()
        if not content:
            raise MessageEmptyError
        if request.file_ids:
            raise AppError(
                code=ErrorCode.FILE_NOT_FOUND,
                message="文件不存在",
                status_code=404,
            )

        run_id = str(uuid4())
        user_message_id = str(uuid4())
        assistant_message_id = str(uuid4())
        timestamp = utc_now()

        try:
            with self._database.session_factory() as session:
                session.execute(text("BEGIN IMMEDIATE"))
                thread_repository = ThreadRepository(session)
                thread = thread_repository.get(thread_id)
                if thread is None:
                    raise ThreadNotFoundError
                if thread_repository.has_active_run(thread_id):
                    raise ThreadBusyError

                run = Run(
                    id=run_id,
                    thread_id=thread_id,
                    status="running",
                    user_message_id=user_message_id,
                    assistant_message_id=None,
                    loop_count=0,
                    started_at=timestamp,
                )
                RunRepository(session).add(run)
                session.flush()

                message_repository = MessageRepository(session)
                message_repository.add(
                    Message(
                        id=user_message_id,
                        thread_id=thread_id,
                        run_id=run_id,
                        role="user",
                        content=content,
                        message_type="text",
                        metadata_json={},
                        sequence_number=message_repository.next_sequence_number(thread_id),
                        created_at=timestamp,
                    )
                )
                thread_repository.touch(thread, timestamp)
                session.flush()
                context = tuple(
                    ModelMessage(role=message.role, content=message.content)
                    for message in message_repository.list_conversation(thread_id)
                )
                session.commit()
        except IntegrityError as exc:
            raise ThreadBusyError from exc

        return PreparedChat(
            thread_id=thread_id,
            run_id=run_id,
            assistant_message_id=assistant_message_id,
            context=context,
        )

    async def stream(self, prepared: PreparedChat) -> AsyncGenerator[str, None]:
        """Yield public SSE frames and finish the persisted run consistently."""
        chunks: list[str] = []
        try:
            yield self._event(prepared, "run_start", {"status": "running"}).encode()
            yield self._event(
                prepared,
                "assistant_start",
                {"message_id": prepared.assistant_message_id},
            ).encode()
            async for chunk in self._model.stream(prepared.context):
                if not chunk:
                    continue
                chunks.append(chunk)
                yield self._event(
                    prepared,
                    "assistant_delta",
                    {
                        "message_id": prepared.assistant_message_id,
                        "content": chunk,
                    },
                ).encode()
            content = "".join(chunks)
            if not content:
                raise ModelClientError("Model returned no text")
            self._complete_success(prepared, content)
        except (asyncio.CancelledError, GeneratorExit):
            self._mark_terminal(
                prepared,
                status="cancelled",
                error_code=None,
                error_message=None,
            )
            raise
        except ModelClientError:
            logger.warning(
                "Model request failed",
                extra={"thread_id": prepared.thread_id, "run_id": prepared.run_id},
            )
            self._mark_terminal(
                prepared,
                status="failed",
                error_code=ErrorCode.MODEL_REQUEST_FAILED.value,
                error_message="模型服务暂时不可用",
            )
            yield self._error_event(
                prepared,
                code=ErrorCode.MODEL_REQUEST_FAILED,
                message="模型服务暂时不可用",
                retryable=True,
            ).encode()
            yield self._event(prepared, "run_end", {"status": "failed", "loop_count": 1}).encode()
            return
        except Exception:
            logger.exception(
                "Chat completion persistence failed",
                extra={"thread_id": prepared.thread_id, "run_id": prepared.run_id},
            )
            self._mark_terminal(
                prepared,
                status="failed",
                error_code=ErrorCode.INTERNAL_ERROR.value,
                error_message="服务器内部错误",
            )
            yield self._error_event(
                prepared,
                code=ErrorCode.INTERNAL_ERROR,
                message="服务器内部错误",
                retryable=False,
            ).encode()
            yield self._event(prepared, "run_end", {"status": "failed", "loop_count": 1}).encode()
            return

        yield self._event(
            prepared,
            "assistant_end",
            {
                "message_id": prepared.assistant_message_id,
                "content": content,
            },
        ).encode()
        yield self._event(prepared, "run_end", {"status": "success", "loop_count": 1}).encode()

    def _complete_success(self, prepared: PreparedChat, content: str) -> None:
        timestamp = utc_now()
        with self._database.session_factory() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            run = RunRepository(session).get_for_thread(
                run_id=prepared.run_id,
                thread_id=prepared.thread_id,
            )
            thread = ThreadRepository(session).get(prepared.thread_id)
            if run is None or thread is None or run.status != "running":
                raise RuntimeError("Active run state was lost")

            messages = MessageRepository(session)
            messages.add(
                Message(
                    id=prepared.assistant_message_id,
                    thread_id=prepared.thread_id,
                    run_id=prepared.run_id,
                    role="assistant",
                    content=content,
                    message_type="text",
                    metadata_json={},
                    sequence_number=messages.next_sequence_number(prepared.thread_id),
                    created_at=timestamp,
                )
            )
            run.status = "success"
            run.assistant_message_id = prepared.assistant_message_id
            run.loop_count = 1
            run.finished_at = timestamp
            if thread.title == "新会话":
                first_user_message = messages.first_user_message(prepared.thread_id)
                if first_user_message is not None:
                    thread.title = self._title_from(first_user_message.content)
            ThreadRepository(session).touch(thread, timestamp)
            session.commit()

    def _mark_terminal(
        self,
        prepared: PreparedChat,
        *,
        status: str,
        error_code: str | None,
        error_message: str | None,
    ) -> None:
        try:
            with self._database.session_factory() as session:
                session.execute(text("BEGIN IMMEDIATE"))
                run = RunRepository(session).get_for_thread(
                    run_id=prepared.run_id,
                    thread_id=prepared.thread_id,
                )
                if run is None or run.status not in ("pending", "running"):
                    session.rollback()
                    return
                run.status = status
                run.loop_count = 1
                run.error_code = error_code
                run.error_message = error_message
                run.finished_at = utc_now()
                session.commit()
        except Exception:
            logger.exception(
                "Failed to persist terminal run state",
                extra={"thread_id": prepared.thread_id, "run_id": prepared.run_id},
            )

    @staticmethod
    def _title_from(content: str) -> str:
        normalized = " ".join(content.split())
        return normalized if len(normalized) <= 30 else f"{normalized[:30]}…"

    @staticmethod
    def _event(
        prepared: PreparedChat,
        event: SseEventName,
        data: dict[str, object],
    ) -> SseEvent:
        return SseEvent(
            event=event,
            thread_id=prepared.thread_id,
            run_id=prepared.run_id,
            data=data,
        )

    @staticmethod
    def _error_event(
        prepared: PreparedChat,
        *,
        code: ErrorCode,
        message: str,
        retryable: bool,
    ) -> SseEvent:
        return SseEvent(
            event="error",
            thread_id=prepared.thread_id,
            run_id=prepared.run_id,
            data={
                "code": code.value,
                "message": message,
                "retryable": retryable,
                "details": {},
            },
        )

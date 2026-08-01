"""Tool-call persistence queries."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.tool_call import ToolCall


class ToolCallRepository:
    """Read and write tool records within a caller-owned transaction."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, tool_call: ToolCall) -> None:
        """Stage a new tool-call record."""
        self._session.add(tool_call)

    def get_for_run(
        self,
        *,
        tool_call_id: str,
        run_id: str,
        thread_id: str,
    ) -> ToolCall | None:
        """Return a tool call only inside the expected run and thread."""
        statement = select(ToolCall).where(
            ToolCall.id == tool_call_id,
            ToolCall.run_id == run_id,
            ToolCall.thread_id == thread_id,
        )
        return self._session.scalar(statement)

    def list_active(self) -> list[ToolCall]:
        """Return tool calls left non-terminal by an interrupted process."""
        statement = select(ToolCall).where(ToolCall.status.in_(("pending", "running")))
        return list(self._session.scalars(statement))

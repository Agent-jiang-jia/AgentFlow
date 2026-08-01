"""Chat request and SSE event schemas."""

import json
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

SseEventName = Literal[
    "run_start",
    "assistant_start",
    "assistant_delta",
    "tool_start",
    "tool_result",
    "artifact_created",
    "assistant_end",
    "run_end",
    "error",
]


class ChatRequest(BaseModel):
    """Plain Phase 2 chat input."""

    message: str = Field(max_length=20_000)
    file_ids: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("file_ids")
    @classmethod
    def deduplicate_file_ids(cls, values: list[str]) -> list[str]:
        """Preserve file order while removing repeated opaque identifiers."""
        return list(dict.fromkeys(values))


class SseEvent(BaseModel):
    """One public server-sent event."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event: SseEventName
    thread_id: str
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any]

    def encode(self) -> str:
        """Encode this event as one standards-compliant SSE frame."""
        payload = json.dumps(
            self.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return f"id: {self.event_id}\nevent: {self.event}\ndata: {payload}\n\n"

"""Message API schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.schemas.pagination import Pagination
from app.schemas.thread import serialize_utc


class MessageResponse(BaseModel):
    """Public persisted message representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    thread_id: str
    run_id: str | None
    role: str
    content: str
    message_type: str
    metadata: dict[str, Any] = Field(validation_alias="metadata_json")
    sequence_number: int
    created_at: datetime

    @field_serializer("created_at")
    def serialize_timestamp(self, value: datetime) -> str:
        """Emit an explicit UTC timestamp."""
        return serialize_utc(value)


class MessagePage(Pagination):
    """Paginated message collection."""

    items: list[MessageResponse]

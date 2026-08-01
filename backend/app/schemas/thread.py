"""Thread API schemas."""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.schemas.pagination import Pagination


def serialize_utc(value: datetime) -> str:
    """Serialize SQLite timestamps as explicit ISO 8601 UTC values."""
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.isoformat().replace("+00:00", "Z")


class ThreadCreate(BaseModel):
    """Optional thread creation input."""

    title: str = Field(default="新会话", min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """Reject titles that become empty after whitespace normalization."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Title cannot be empty")
        return normalized


class ThreadResponse(BaseModel):
    """Public thread representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        """Emit explicit UTC timestamps."""
        return serialize_utc(value)


class ThreadPage(Pagination):
    """Paginated thread collection."""

    items: list[ThreadResponse]

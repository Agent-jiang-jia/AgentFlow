"""File API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_serializer

from app.schemas.pagination import Pagination
from app.schemas.thread import serialize_utc

FileCategory = Literal["upload", "parsed", "artifact"]
FileCategoryFilter = Literal["all", "upload", "parsed", "artifact"]


class FileResponse(BaseModel):
    """Safe public metadata without a server filesystem path."""

    id: str
    thread_id: str
    source_file_id: str | None
    category: FileCategory
    original_name: str
    extension: str | None
    mime_type: str | None
    size_bytes: int
    parse_status: str | None
    parse_error: str | None
    parsed_file_id: str | None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_timestamp(self, value: datetime) -> str:
        """Emit an explicit UTC timestamp."""
        return serialize_utc(value)


class FileUploadResponse(BaseModel):
    """Upload wrapper reserved by the API contract."""

    file: FileResponse


class FilePage(Pagination):
    """Paginated thread-owned file collection."""

    items: list[FileResponse]

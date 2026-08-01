"""Shared pagination response fields."""

from pydantic import BaseModel, Field


class Pagination(BaseModel):
    """One-based pagination metadata."""

    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)

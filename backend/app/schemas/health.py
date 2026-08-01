"""Health endpoint schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Successful API health response."""

    model_config = ConfigDict(frozen=True)

    status: Literal["healthy"]
    service: str
    version: str
    database: Literal["ok"]

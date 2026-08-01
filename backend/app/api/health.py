"""Health check API."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_health_service
from app.schemas.health import HealthResponse
from app.services.health_service import HealthService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health(
    service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthResponse:
    """Report process and SQLite connectivity."""
    return service.check()

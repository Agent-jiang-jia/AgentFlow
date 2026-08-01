"""FastAPI dependency providers."""

from typing import cast

from fastapi import Request

from app.core.config import Settings
from app.db.database import Database
from app.services.health_service import HealthService


def get_health_service(request: Request) -> HealthService:
    """Resolve the health service from application-owned resources."""
    database = cast(Database, request.app.state.database)
    settings = cast(Settings, request.app.state.settings)
    return HealthService(database=database, settings=settings)

"""Health check orchestration."""

from app.core.config import Settings
from app.core.exceptions import DatabaseUnavailableError
from app.db.database import Database
from app.schemas.health import HealthResponse


class HealthService:
    """Build a health response from real infrastructure checks."""

    def __init__(self, *, database: Database, settings: Settings) -> None:
        self._database = database
        self._settings = settings

    def check(self) -> HealthResponse:
        """Return health status or raise a safe availability error."""
        if not self._database.is_healthy():
            raise DatabaseUnavailableError()
        return HealthResponse(
            status="healthy",
            service="agentflow-api",
            version=self._settings.app_version,
            database="ok",
        )

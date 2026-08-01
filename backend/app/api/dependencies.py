"""FastAPI dependency providers."""

from typing import cast

from fastapi import Request

from app.core.config import Settings
from app.db.database import Database
from app.services.chat_service import ChatService
from app.services.health_service import HealthService
from app.services.model_client import ChatModel
from app.services.thread_service import ThreadService
from app.storage.thread_storage import ThreadStorage


def get_health_service(request: Request) -> HealthService:
    """Resolve the health service from application-owned resources."""
    database = cast(Database, request.app.state.database)
    settings = cast(Settings, request.app.state.settings)
    return HealthService(database=database, settings=settings)


def get_thread_service(request: Request) -> ThreadService:
    """Resolve thread orchestration from application-owned resources."""
    database = cast(Database, request.app.state.database)
    settings = cast(Settings, request.app.state.settings)
    return ThreadService(
        database=database,
        storage=ThreadStorage(settings.resolved_data_dir),
    )


def get_chat_service(request: Request) -> ChatService:
    """Resolve plain chat orchestration and its fixed model."""
    database = cast(Database, request.app.state.database)
    model = cast(ChatModel, request.app.state.model_client)
    return ChatService(database=database, model=model)

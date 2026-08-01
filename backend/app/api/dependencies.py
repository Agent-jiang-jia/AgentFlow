"""FastAPI dependency providers."""

from typing import cast

from fastapi import Request

from app.agent.runtime import AgentRuntime
from app.core.config import Settings
from app.db.database import Database
from app.services.chat_service import ChatService
from app.services.health_service import HealthService
from app.services.model_client import ChatModel
from app.services.source_service import SourceService
from app.services.thread_service import ThreadService
from app.services.web_fetch_service import WebFetchService
from app.services.web_search_service import WebSearchService
from app.storage.thread_storage import ThreadStorage
from app.tools import create_phase_four_registry
from app.tools.executor import ToolExecutor


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
    """Resolve the bounded single-agent orchestration and its fixed model."""
    database = cast(Database, request.app.state.database)
    settings = cast(Settings, request.app.state.settings)
    model = cast(ChatModel, request.app.state.model_client)
    search_service = cast(WebSearchService, request.app.state.web_search_service)
    fetch_service = cast(WebFetchService, request.app.state.web_fetch_service)
    registry = create_phase_four_registry(
        search_service=search_service,
        fetch_service=fetch_service,
        source_service=SourceService(database),
    )
    executor = ToolExecutor(
        database=database,
        registry=registry,
        timeout_seconds=settings.tool_timeout_seconds,
    )
    runtime = AgentRuntime(
        model=model,
        registry=registry,
        executor=executor,
        max_loops=settings.max_agent_loops,
    )
    return ChatService(database=database, runtime=runtime)

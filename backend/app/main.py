"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response

from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.threads import router as threads_router
from app.core.config import Settings, get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.db.database import Database
from app.services.model_client import OpenAICompatibleChatModel
from app.services.web_fetch_service import WebFetchService
from app.services.web_search_service import WebSearchService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an independently configurable FastAPI application."""
    app_settings = settings or get_settings()
    configure_logging(app_settings.log_level)
    database = Database(app_settings.resolved_database_path)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        app_settings.ensure_directories()
        logger.info("AgentFlow API started", extra={"environment": app_settings.environment})
        try:
            yield
        finally:
            database.dispose()
            logger.info("AgentFlow API stopped")

    application = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        lifespan=lifespan,
    )
    application.state.settings = app_settings
    application.state.database = database
    application.state.model_client = OpenAICompatibleChatModel(app_settings)
    application.state.web_search_service = WebSearchService(
        provider=app_settings.search_provider,
        api_base=app_settings.search_api_base,
        api_key=app_settings.search_api_key,
        timeout_seconds=app_settings.search_timeout_seconds,
    )
    application.state.web_fetch_service = WebFetchService(
        timeout_seconds=app_settings.web_fetch_timeout_seconds,
        max_bytes=app_settings.web_fetch_max_bytes,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def add_request_id(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    register_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(threads_router)
    application.include_router(chat_router)
    return application


app = create_app()

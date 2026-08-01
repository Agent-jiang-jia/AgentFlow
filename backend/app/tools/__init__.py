"""Registered tools available to the single AgentFlow runtime."""

from app.services.artifact_service import ArtifactService
from app.services.file_service import FileService
from app.services.source_service import SourceService
from app.services.web_fetch_service import WebFetchService
from app.services.web_search_service import WebSearchService
from app.tools.get_current_time import create_get_current_time_tool
from app.tools.list_files import create_list_files_tool
from app.tools.read_file import create_read_file_tool
from app.tools.registry import ToolRegistry
from app.tools.web_fetch import create_web_fetch_tool
from app.tools.web_search import create_web_search_tool
from app.tools.write_file import create_write_file_tool


def create_phase_three_registry() -> ToolRegistry:
    """Create the Phase 3 registry without any later-phase product tools."""
    registry = ToolRegistry()
    registry.register(create_get_current_time_tool())
    return registry


def create_phase_four_registry(
    *,
    search_service: WebSearchService,
    fetch_service: WebFetchService,
    source_service: SourceService,
) -> ToolRegistry:
    """Create the Phase 4 registry with the two approved public-web tools."""
    registry = create_phase_three_registry()
    registry.register(create_web_search_tool(search_service, source_service))
    registry.register(create_web_fetch_tool(fetch_service, source_service))
    return registry


def create_phase_five_registry(
    *,
    search_service: WebSearchService,
    fetch_service: WebFetchService,
    source_service: SourceService,
    file_service: FileService,
) -> ToolRegistry:
    """Create the Phase 5 registry with thread-scoped file read tools."""
    registry = create_phase_four_registry(
        search_service=search_service,
        fetch_service=fetch_service,
        source_service=source_service,
    )
    registry.register(create_list_files_tool(file_service))
    registry.register(create_read_file_tool(file_service))
    return registry


def create_phase_six_registry(
    *,
    search_service: WebSearchService,
    fetch_service: WebFetchService,
    source_service: SourceService,
    file_service: FileService,
    artifact_service: ArtifactService,
) -> ToolRegistry:
    """Create the Phase 6 registry with safe generated-file delivery."""
    registry = create_phase_five_registry(
        search_service=search_service,
        fetch_service=fetch_service,
        source_service=source_service,
        file_service=file_service,
    )
    registry.register(create_write_file_tool(artifact_service))
    return registry


__all__ = [
    "ToolRegistry",
    "create_phase_five_registry",
    "create_phase_four_registry",
    "create_phase_six_registry",
    "create_phase_three_registry",
]

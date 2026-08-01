"""Model-facing web_search tool."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.error_codes import ErrorCode
from app.services.source_service import SourceInput, SourceService
from app.services.web_search_service import WebSearchService, WebSearchServiceError
from app.tools.base import Tool, ToolContext, ToolError, ToolFailure, ToolOutput


class WebSearchArguments(BaseModel):
    """Validated search parameters exposed to the model."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, max_length=500, description="Chinese or English search query.")
    max_results: int = Field(default=5, ge=1, le=10, description="Number of results, at most 10.")

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        """Reject whitespace-only queries and normalize surrounding spaces."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("Search query cannot be empty")
        return normalized


def create_web_search_tool(
    service: WebSearchService,
    source_service: SourceService,
) -> Tool:
    """Create the configured web-search tool."""

    async def search(context: ToolContext, arguments: BaseModel) -> ToolOutput:
        if not isinstance(arguments, WebSearchArguments):
            raise TypeError("Validated web_search arguments were not provided")
        try:
            results = await service.search(
                query=arguments.query,
                max_results=arguments.max_results,
            )
        except WebSearchServiceError as exc:
            raise ToolFailure(
                ToolError(
                    code=ErrorCode.WEB_SEARCH_FAILED,
                    message=str(exc),
                    retryable=exc.retryable,
                )
            ) from exc
        source_service.record(
            run_id=context.run_id,
            thread_id=context.thread_id,
            sources=tuple(
                SourceInput(
                    title=result.title,
                    url=result.url,
                    snippet=result.snippet,
                    source_type="search",
                )
                for result in results
            ),
        )
        return ToolOutput(
            summary=f"找到 {len(results)} 条搜索结果",
            data={
                "query": arguments.query,
                "results": [
                    {"title": item.title, "url": item.url, "snippet": item.snippet}
                    for item in results
                ],
            },
        )

    return Tool(
        name="web_search",
        description=(
            "Search the public web using Chinese or English keywords. Returns titles, URLs, "
            "and snippets; it does not summarize the results."
        ),
        display_name="正在搜索互联网",
        arguments_schema=WebSearchArguments,
        handler=search,
        public_argument_names=("query", "max_results"),
    )

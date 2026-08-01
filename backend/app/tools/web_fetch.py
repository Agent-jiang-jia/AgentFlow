"""Model-facing web_fetch tool."""

from pydantic import BaseModel, ConfigDict, Field

from app.core.error_codes import ErrorCode
from app.core.security import UrlNotAllowedError
from app.services.source_service import SourceInput, SourceService
from app.services.web_fetch_service import WebFetchService, WebFetchServiceError
from app.tools.base import Tool, ToolContext, ToolError, ToolFailure, ToolOutput


class WebFetchArguments(BaseModel):
    """Validated webpage-reading parameters exposed to the model."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=2048, description="Public HTTP or HTTPS URL.")
    max_chars: int = Field(
        default=20_000,
        ge=1_000,
        le=100_000,
        description="Maximum extracted正文 characters returned to the model.",
    )


def create_web_fetch_tool(
    service: WebFetchService,
    source_service: SourceService,
) -> Tool:
    """Create the SSRF-protected webpage reader."""

    async def fetch(context: ToolContext, arguments: BaseModel) -> ToolOutput:
        if not isinstance(arguments, WebFetchArguments):
            raise TypeError("Validated web_fetch arguments were not provided")
        try:
            page = await service.fetch(url=arguments.url, max_chars=arguments.max_chars)
        except UrlNotAllowedError as exc:
            raise ToolFailure(
                ToolError(code=ErrorCode.URL_NOT_ALLOWED, message="URL 不允许访问")
            ) from exc
        except WebFetchServiceError as exc:
            raise ToolFailure(
                ToolError(
                    code=ErrorCode.WEB_FETCH_FAILED,
                    message=str(exc),
                    retryable=exc.retryable,
                )
            ) from exc
        source_service.record(
            run_id=context.run_id,
            thread_id=context.thread_id,
            sources=(
                SourceInput(
                    title=page.title,
                    url=page.url,
                    snippet=page.content[:500],
                    source_type="web_page",
                ),
            ),
        )
        return ToolOutput(
            summary=f"已读取网页: {page.title}"[:500],
            data={
                "title": page.title,
                "url": page.url,
                "content": page.content,
                "truncated": page.truncated,
            },
        )

    return Tool(
        name="web_fetch",
        description=(
            "Read and extract the main text from a public HTTP(S) webpage. "
            "Use this for URLs supplied by the user or returned by web_search."
        ),
        display_name="正在读取网页",
        arguments_schema=WebFetchArguments,
        handler=fetch,
        public_argument_names=("url", "max_chars"),
        stream_argument_names=("max_chars",),
    )

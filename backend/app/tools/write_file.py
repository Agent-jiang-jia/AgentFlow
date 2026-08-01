"""Model-facing safe Artifact generation tool."""

from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import AppError
from app.services.artifact_service import ArtifactService
from app.tools.base import Tool, ToolContext, ToolError, ToolFailure, ToolOutput


class WriteFileArguments(BaseModel):
    """A leaf filename, UTF-8 content, and optional user-facing description."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    content: str
    description: str | None = Field(default=None, max_length=500)


def create_write_file_tool(artifact_service: ArtifactService) -> Tool:
    """Create the current-thread-only write_file tool."""

    async def write_file(context: ToolContext, raw_arguments: BaseModel) -> ToolOutput:
        arguments = WriteFileArguments.model_validate(raw_arguments.model_dump())
        try:
            artifact = artifact_service.write(
                thread_id=context.thread_id,
                filename=arguments.filename,
                content=arguments.content,
                description=arguments.description,
            )
        except AppError as exc:
            raise ToolFailure(
                ToolError(code=exc.code, message=exc.message, retryable=exc.retryable)
            ) from exc
        preview_url = f"/api/threads/{context.thread_id}/artifacts/{artifact.id}/preview"
        download_url = f"/api/threads/{context.thread_id}/artifacts/{artifact.id}/download"
        return ToolOutput(
            summary=f"文件已生成: {artifact.original_name}",
            data={
                "file_id": artifact.id,
                "filename": artifact.original_name,
                "description": artifact.description or "",
                "preview_url": preview_url,
                "download_url": download_url,
            },
        )

    return Tool(
        name="write_file",
        description=(
            "Create a UTF-8 file in the current conversation outputs. Supported extensions: "
            ".md, .txt, .html, .csv, .json, .py, .js, .ts, .yaml, and .yml."
        ),
        display_name="正在生成文件",
        arguments_schema=WriteFileArguments,
        handler=write_file,
        public_argument_names=("filename", "description"),
        stream_argument_names=("filename", "description"),
    )

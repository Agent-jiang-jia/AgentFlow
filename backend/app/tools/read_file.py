"""Model-facing bounded text reads by opaque file identifier."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.exceptions import AppError
from app.services.file_service import FileService
from app.tools.base import Tool, ToolContext, ToolError, ToolFailure, ToolOutput


class ReadFileArguments(BaseModel):
    """Safe file identity and bounded line/character window."""

    model_config = ConfigDict(extra="forbid")

    file_id: str
    start_line: int = Field(default=1, ge=1)
    max_lines: int = Field(default=200, ge=1, le=2_000)
    max_chars: int = Field(default=50_000, ge=1, le=100_000)

    @field_validator("file_id")
    @classmethod
    def validate_file_id(cls, value: str) -> str:
        """Accept canonical UUIDs only, never paths or filenames."""
        parsed = UUID(value)
        if str(parsed) != value:
            raise ValueError("File identifier is not canonical")
        return value


def create_read_file_tool(file_service: FileService) -> Tool:
    """Create the thread-scoped read_file tool."""

    async def read_file(context: ToolContext, raw_arguments: BaseModel) -> ToolOutput:
        arguments = ReadFileArguments.model_validate(raw_arguments.model_dump())
        try:
            result = file_service.read_for_tool(
                thread_id=context.thread_id,
                file_id=arguments.file_id,
                start_line=arguments.start_line,
                max_lines=arguments.max_lines,
                max_chars=arguments.max_chars,
            )
        except AppError as exc:
            raise ToolFailure(
                ToolError(code=exc.code, message=exc.message, retryable=exc.retryable)
            ) from exc
        return ToolOutput(
            summary=f"已读取文件 {result.filename} 的第 {result.start_line}-{result.end_line} 行",
            data={
                "file_id": result.file_id,
                "filename": result.filename,
                "content": result.content,
                "start_line": result.start_line,
                "end_line": result.end_line,
                "total_lines": result.total_lines,
                "truncated": result.truncated,
            },
        )

    return Tool(
        name="read_file",
        description=(
            "Read normalized UTF-8 text for a current-conversation file by file_id only. "
            "Binary uploads automatically use their parsed derivative."
        ),
        display_name="正在查看上传文件",
        arguments_schema=ReadFileArguments,
        handler=read_file,
        public_argument_names=("file_id", "start_line", "max_lines", "max_chars"),
        stream_argument_names=("file_id", "start_line", "max_lines", "max_chars"),
    )

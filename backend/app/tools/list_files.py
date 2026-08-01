"""Model-facing metadata listing for the current thread."""

from pydantic import BaseModel, ConfigDict

from app.core.exceptions import AppError
from app.services.file_service import FileService
from app.tools.base import Tool, ToolContext, ToolError, ToolFailure, ToolOutput


class ListFilesArguments(BaseModel):
    """The current thread is supplied exclusively by server context."""

    model_config = ConfigDict(extra="forbid")


def create_list_files_tool(file_service: FileService) -> Tool:
    """Create the thread-scoped list_files tool."""

    async def list_files(context: ToolContext, _arguments: BaseModel) -> ToolOutput:
        try:
            files = file_service.list_for_tool(thread_id=context.thread_id)
        except AppError as exc:
            raise ToolFailure(
                ToolError(code=exc.code, message=exc.message, retryable=exc.retryable)
            ) from exc
        return ToolOutput(
            summary=f"当前会话共有 {len(files)} 个文件记录",
            data={"files": files, "count": len(files)},
        )

    return Tool(
        name="list_files",
        description=(
            "List uploaded, parsed, and generated files available in the current conversation. "
            "Use this before read_file when the user has not provided a file_id."
        ),
        display_name="正在查看上传文件",
        arguments_schema=ListFilesArguments,
        handler=list_files,
        public_argument_names=(),
    )

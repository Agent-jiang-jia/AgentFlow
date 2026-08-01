"""Core types shared by the tool registry and executor."""

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from pydantic import BaseModel

from app.core.error_codes import ErrorCode

ToolHandler = Callable[["ToolContext", BaseModel], Awaitable["ToolOutput"]]


@dataclass(frozen=True, slots=True)
class ToolContext:
    """Server-owned execution context that model arguments cannot override."""

    thread_id: str
    run_id: str


@dataclass(frozen=True, slots=True)
class ToolOutput:
    """Successful structured output returned by a tool implementation."""

    summary: str
    data: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolError:
    """Safe structured tool failure returned to the model and public stream."""

    code: ErrorCode
    message: str
    retryable: bool = False

    def as_dict(self) -> dict[str, object]:
        """Return the public error payload."""
        return {
            "code": self.code.value,
            "message": self.message,
            "retryable": self.retryable,
        }


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Provider-neutral function definition exposed to the fixed model."""

    name: str
    description: str
    parameters: dict[str, object]

    def as_openai_tool(self) -> dict[str, object]:
        """Return the OpenAI-compatible function-tool envelope."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass(frozen=True, slots=True)
class Tool:
    """One registered tool with a Pydantic argument contract."""

    name: str
    description: str
    display_name: str
    arguments_schema: type[BaseModel]
    handler: ToolHandler
    public_argument_names: tuple[str, ...]

    def definition(self) -> ToolDefinition:
        """Build the function definition sent to the model."""
        schema = self.arguments_schema.model_json_schema()
        return ToolDefinition(
            name=self.name,
            description=self.description,
            parameters={str(key): value for key, value in schema.items()},
        )

    def safe_arguments(self, arguments: Mapping[str, object]) -> dict[str, object]:
        """Keep only explicitly public arguments for persistence and SSE."""
        return {
            name: _safe_value(arguments[name])
            for name in self.public_argument_names
            if name in arguments
        }

    async def execute(self, context: ToolContext, arguments: BaseModel) -> ToolOutput:
        """Run the registered asynchronous handler."""
        return await self.handler(context, arguments)


def _safe_value(value: object) -> object:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return value if len(value) <= 200 else f"{value[:200]}…"
    if isinstance(value, list):
        return [_safe_value(item) for item in value[:20]]
    if isinstance(value, Mapping):
        return {
            str(key): _safe_value(item)
            for key, item in list(value.items())[:20]
            if isinstance(key, str)
        }
    return str(value)[:200]

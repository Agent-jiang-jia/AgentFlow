"""Tool registration, lookup, and model definition discovery."""

from app.tools.base import Tool, ToolDefinition


class ToolRegistry:
    """Own the unique set of tools available to the single agent."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register one tool and reject ambiguous duplicate names."""
        if not tool.name or tool.name in self._tools:
            raise ValueError(f"Tool name is empty or already registered: {tool.name!r}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Return a registered tool by its exact model-facing name."""
        return self._tools.get(name)

    def definitions(self) -> tuple[ToolDefinition, ...]:
        """Return stable model-facing definitions in registration order."""
        return tuple(tool.definition() for tool in self._tools.values())

    def display_name(self, name: str) -> str:
        """Return an allow-listed public status label."""
        tool = self.get(name)
        return tool.display_name if tool is not None else "正在分析问题"

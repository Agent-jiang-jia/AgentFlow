"""Registered tools available to the single AgentFlow runtime."""

from app.tools.get_current_time import create_get_current_time_tool
from app.tools.registry import ToolRegistry


def create_phase_three_registry() -> ToolRegistry:
    """Create the Phase 3 registry without any later-phase product tools."""
    registry = ToolRegistry()
    registry.register(create_get_current_time_tool())
    return registry


__all__ = ["ToolRegistry", "create_phase_three_registry"]

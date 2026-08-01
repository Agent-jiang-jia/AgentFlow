"""Tool Registry and Phase 3 test-tool unit tests."""

import pytest
from app.tools import create_phase_three_registry
from app.tools.base import ToolContext
from pydantic import ValidationError


@pytest.mark.anyio
async def test_registry_exposes_schema_and_invokes_validated_test_tool() -> None:
    """Registration, lookup, Pydantic validation, and invocation form one contract."""
    registry = create_phase_three_registry()
    tool = registry.get("get_current_time")
    assert tool is not None
    assert registry.get("missing") is None
    definition = registry.definitions()[0]
    assert definition.name == "get_current_time"
    assert definition.parameters["additionalProperties"] is False

    arguments = tool.arguments_schema.model_validate({"timezone": "+08:00"})
    output = await tool.execute(
        ToolContext(thread_id="opaque-thread", run_id="opaque-run"),
        arguments,
    )
    assert output.data["timezone"] == "+08:00"
    assert isinstance(output.data["iso_time"], str)

    with pytest.raises(ValidationError):
        tool.arguments_schema.model_validate({"timezone": "Asia/Shanghai"})


def test_registry_rejects_duplicate_tool_names() -> None:
    """A model-facing name can resolve to exactly one implementation."""
    registry = create_phase_three_registry()
    existing = registry.get("get_current_time")
    assert existing is not None
    with pytest.raises(ValueError):
        registry.register(existing)

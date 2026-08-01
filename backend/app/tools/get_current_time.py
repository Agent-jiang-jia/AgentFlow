"""Small Phase 3 tool used to prove the complete agent loop."""

import re
from datetime import UTC, datetime, timedelta, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.tools.base import Tool, ToolContext, ToolOutput

UTC_OFFSET_PATTERN = re.compile(r"^[+-](?:0\d|1[0-4]):[0-5]\d$")


class GetCurrentTimeArguments(BaseModel):
    """Arguments accepted by the deterministic current-time tool."""

    model_config = ConfigDict(extra="forbid")

    timezone: str = Field(
        default="UTC",
        description="UTC or a numeric UTC offset such as +08:00 or -05:00.",
    )

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        """Accept UTC and portable numeric offsets without platform timezone data."""
        normalized = value.strip().upper()
        if normalized == "UTC":
            return normalized
        if not UTC_OFFSET_PATTERN.fullmatch(normalized):
            raise ValueError("Timezone must be UTC or a numeric UTC offset")
        hours, minutes = (int(part) for part in normalized[1:].split(":"))
        if hours == 14 and minutes != 0:
            raise ValueError("UTC offsets cannot exceed 14 hours")
        return normalized


async def _get_current_time(
    context: ToolContext,
    arguments: BaseModel,
) -> ToolOutput:
    if not isinstance(arguments, GetCurrentTimeArguments):
        raise TypeError("Validated get_current_time arguments were not provided")
    if arguments.timezone == "UTC":
        target_timezone = UTC
    else:
        sign = 1 if arguments.timezone[0] == "+" else -1
        hours, minutes = (int(part) for part in arguments.timezone[1:].split(":"))
        target_timezone = timezone(sign * timedelta(hours=hours, minutes=minutes))

    current = datetime.now(target_timezone)
    return ToolOutput(
        summary=f"已获取 {arguments.timezone} 当前时间",
        data={
            "timezone": arguments.timezone,
            "iso_time": current.isoformat(timespec="seconds"),
        },
    )


def create_get_current_time_tool() -> Tool:
    """Create the temporary Phase 3 validation tool."""
    return Tool(
        name="get_current_time",
        description=(
            "Get the current date and time in UTC or a numeric UTC offset. "
            "Use this only when the user asks for the current time or date."
        ),
        display_name="正在查询当前时间",
        arguments_schema=GetCurrentTimeArguments,
        handler=_get_current_time,
        public_argument_names=("timezone",),
    )

"""LangGraph assistant/tools loop for one sequential agent run."""

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from contextlib import suppress
from dataclasses import dataclass
from typing import Annotated, Literal, TypedDict
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from app.core.error_codes import ErrorCode
from app.services.model_client import (
    ChatModel,
    ModelClientError,
    ModelToolCallDelta,
)
from app.tools.base import ToolContext, ToolError
from app.tools.executor import ToolExecution, ToolExecutor
from app.tools.registry import ToolRegistry

AgentTerminalStatus = Literal["success", "max_loops_reached"]


@dataclass(frozen=True, slots=True)
class AgentTextDelta:
    """Public assistant text produced by a model turn."""

    content: str


@dataclass(frozen=True, slots=True)
class AgentLoopStarted:
    """Internal observation used to persist the actual model-loop count."""

    loop_count: int


@dataclass(frozen=True, slots=True)
class AgentToolStart:
    """Public, allow-listed tool execution start."""

    tool_call_id: str
    tool_name: str
    display_name: str
    arguments: dict[str, object]


@dataclass(frozen=True, slots=True)
class AgentToolResult:
    """Public safe summary of one terminal tool invocation."""

    execution: ToolExecution


@dataclass(frozen=True, slots=True)
class AgentFinished:
    """Successful or policy-limited terminal graph outcome."""

    status: AgentTerminalStatus
    content: str
    loop_count: int


@dataclass(frozen=True, slots=True)
class AgentFailed:
    """Internal graph failure propagated to chat orchestration."""

    error: Exception


type AgentEvent = (
    AgentLoopStarted
    | AgentTextDelta
    | AgentToolStart
    | AgentToolResult
    | AgentFinished
    | AgentFailed
)


@dataclass(frozen=True, slots=True)
class PendingToolCall:
    """One complete model-requested tool call awaiting sequential execution."""

    tool_call_id: str
    tool_name: str
    raw_arguments: str
    decoded_arguments: object


class AgentState(TypedDict):
    """Mutable state passed between the LangGraph assistant and tools nodes."""

    messages: Annotated[list[BaseMessage], add_messages]
    loop_count: int
    pending_tool_calls: list[PendingToolCall]
    visible_content: str
    last_tool_signature: str | None
    termination: AgentTerminalStatus | None


class AgentStateUpdate(TypedDict, total=False):
    """Partial state returned by one graph node."""

    messages: list[BaseMessage]
    loop_count: int
    pending_tool_calls: list[PendingToolCall]
    visible_content: str
    last_tool_signature: str | None
    termination: AgentTerminalStatus | None


@dataclass(slots=True)
class _ToolCallAssembly:
    provider_id: str = ""
    name: str = ""
    arguments: str = ""


class AgentRuntime:
    """Run one model and its registered tools through a bounded LangGraph loop."""

    def __init__(
        self,
        *,
        model: ChatModel,
        registry: ToolRegistry,
        executor: ToolExecutor,
        max_loops: int,
    ) -> None:
        self._model = model
        self._registry = registry
        self._executor = executor
        self._max_loops = max_loops

    async def stream(
        self,
        *,
        thread_id: str,
        run_id: str,
        messages: Sequence[BaseMessage],
    ) -> AsyncIterator[AgentEvent]:
        """Yield public runtime updates while LangGraph executes in the background."""
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
        graph = self._build_graph(
            context=ToolContext(thread_id=thread_id, run_id=run_id),
            queue=queue,
        )
        initial_state = AgentState(
            messages=list(messages),
            loop_count=0,
            pending_tool_calls=[],
            visible_content="",
            last_tool_signature=None,
            termination=None,
        )

        async def run_graph() -> None:
            try:
                result = await graph.ainvoke(
                    initial_state,
                    config={"recursion_limit": self._max_loops * 2 + 4},
                )
                termination = result["termination"]
                status: AgentTerminalStatus = termination if termination is not None else "success"
                await queue.put(
                    AgentFinished(
                        status=status,
                        content=result["visible_content"],
                        loop_count=result["loop_count"],
                    )
                )
            except Exception as exc:
                await queue.put(AgentFailed(error=exc))

        task = asyncio.create_task(run_graph())
        try:
            while True:
                event = await queue.get()
                yield event
                if isinstance(event, AgentFinished | AgentFailed):
                    break
        finally:
            if not task.done():
                task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    def _build_graph(
        self,
        *,
        context: ToolContext,
        queue: asyncio.Queue[AgentEvent],
    ) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
        async def assistant_node(state: AgentState) -> AgentStateUpdate:
            next_loop = state["loop_count"] + 1
            await queue.put(AgentLoopStarted(loop_count=next_loop))
            turn_chunks: list[str] = []
            assemblies: dict[int, _ToolCallAssembly] = {}

            async for chunk in self._model.stream(
                state["messages"],
                self._registry.definitions(),
            ):
                if chunk.content:
                    turn_chunks.append(chunk.content)
                    await queue.put(AgentTextDelta(content=chunk.content))
                for tool_delta in chunk.tool_calls:
                    self._accumulate_tool_call(assemblies, tool_delta)

            turn_content = "".join(turn_chunks)
            pending_calls = self._pending_calls(assemblies)
            if not turn_content and not pending_calls:
                raise ModelClientError("Model returned no text or tool calls")

            additional_kwargs: dict[str, object] = {}
            if pending_calls:
                additional_kwargs["tool_calls"] = [
                    {
                        "id": call.tool_call_id,
                        "type": "function",
                        "function": {
                            "name": call.tool_name,
                            "arguments": call.raw_arguments,
                        },
                    }
                    for call in pending_calls
                ]
            assistant_message = AIMessage(
                content=turn_content,
                additional_kwargs=additional_kwargs,
            )
            return AgentStateUpdate(
                messages=[assistant_message],
                loop_count=next_loop,
                pending_tool_calls=pending_calls,
                visible_content=f"{state['visible_content']}{turn_content}",
            )

        async def tools_node(state: AgentState) -> AgentStateUpdate:
            tool_messages: list[BaseMessage] = []
            previous_signature = state["last_tool_signature"]
            max_reached = state["loop_count"] >= self._max_loops
            for pending in state["pending_tool_calls"]:
                forced_rejection = (
                    ToolError(
                        code=ErrorCode.MAX_AGENT_LOOPS_REACHED,
                        message="任务执行步骤过多。已停止继续调用工具",
                    )
                    if max_reached
                    else None
                )
                invocation = self._executor.prepare(
                    context=context,
                    tool_call_id=pending.tool_call_id,
                    tool_name=pending.tool_name,
                    raw_arguments=pending.decoded_arguments,
                    previous_signature=previous_signature,
                    forced_rejection=forced_rejection,
                )
                await queue.put(
                    AgentToolStart(
                        tool_call_id=pending.tool_call_id,
                        tool_name=pending.tool_name,
                        display_name=self._executor.display_name(pending.tool_name),
                        arguments=self._executor.stream_arguments(
                            pending.tool_name,
                            invocation.public_arguments,
                        ),
                    )
                )
                execution = await self._executor.execute(invocation)
                await queue.put(AgentToolResult(execution=execution))
                tool_messages.append(
                    ToolMessage(
                        content=json.dumps(
                            execution.model_payload(),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        tool_call_id=pending.tool_call_id,
                        name=pending.tool_name,
                        status="success" if execution.success else "error",
                    )
                )
                previous_signature = invocation.signature

            return AgentStateUpdate(
                messages=tool_messages,
                pending_tool_calls=[],
                last_tool_signature=previous_signature,
                termination="max_loops_reached" if max_reached else None,
            )

        def after_assistant(state: AgentState) -> Literal["tools", "end"]:
            return "tools" if state["pending_tool_calls"] else "end"

        def after_tools(state: AgentState) -> Literal["assistant", "end"]:
            return "end" if state["termination"] is not None else "assistant"

        builder = StateGraph(AgentState)
        builder.add_node("assistant", assistant_node)
        builder.add_node("tools", tools_node)
        builder.add_edge(START, "assistant")
        builder.add_conditional_edges(
            "assistant",
            after_assistant,
            {"tools": "tools", "end": END},
        )
        builder.add_conditional_edges(
            "tools",
            after_tools,
            {"assistant": "assistant", "end": END},
        )
        return builder.compile()

    @staticmethod
    def _accumulate_tool_call(
        assemblies: dict[int, _ToolCallAssembly],
        delta: ModelToolCallDelta,
    ) -> None:
        assembly = assemblies.setdefault(delta.index, _ToolCallAssembly())
        assembly.provider_id = f"{assembly.provider_id}{delta.provider_id}"
        assembly.name = f"{assembly.name}{delta.name}"
        assembly.arguments = f"{assembly.arguments}{delta.arguments}"

    @staticmethod
    def _pending_calls(
        assemblies: dict[int, _ToolCallAssembly],
    ) -> list[PendingToolCall]:
        pending: list[PendingToolCall] = []
        for index in sorted(assemblies):
            assembly = assemblies[index]
            raw_arguments = assembly.arguments or "{}"
            try:
                decoded_arguments: object = json.loads(raw_arguments)
            except json.JSONDecodeError:
                decoded_arguments = raw_arguments
            pending.append(
                PendingToolCall(
                    tool_call_id=str(uuid4()),
                    tool_name=assembly.name[:100],
                    raw_arguments=raw_arguments,
                    decoded_arguments=decoded_arguments,
                )
            )
        return pending

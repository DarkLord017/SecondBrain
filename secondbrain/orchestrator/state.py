from dataclasses import dataclass, field
from typing import Annotated, Any, Literal, TypedDict


class PlanStep(TypedDict):
    tool: str
    query: str
    wave: int


@dataclass
class ToolResult:
    tool: str
    ok: bool
    chunks: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def merge_tool_results(left: dict[str, ToolResult], right: dict[str, ToolResult]) -> dict[str, ToolResult]:
    return {**left, **right}


class GraphState(TypedDict):
    user_id: str
    notebook_id: str
    session_id: str
    question: str

    notebook_context: dict[str, Any]
    warmup_answer: str | None

    plan: list[PlanStep]
    current_wave: int
    tool_results: Annotated[dict[str, ToolResult], merge_tool_results]
    retries: int

    route_decision: Literal["fan_out", "warm_up", "writer", "retry", "next_wave", "finish"]
    final_answer: str | None
    citations: list[dict[str, Any]]
    error: str | None

from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


@dataclass
class ToolResult:
    tool: str
    ok: bool
    chunks: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


class GraphState(TypedDict):
    user_id: str
    notebook_id: str
    question: str

    messages: Annotated[list[AnyMessage], add_messages]

    notebook_context: dict[str, Any]

    tool_results: dict[str, ToolResult]
    agent_steps: int

    final_answer: str | None
    citations: list[dict[str, Any]]
    citation_flags: list[dict[str, Any]]
    error: str | None

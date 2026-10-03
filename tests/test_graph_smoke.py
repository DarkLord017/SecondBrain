import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from secondbrain.orchestrator import nodes
from secondbrain.orchestrator.graph import build_graph
from secondbrain.orchestrator.registry import TOOL_REGISTRY, register
from secondbrain.orchestrator.state import ToolResult


class FakeTool:
    name = "fake_tool"
    description = "A fake tool used only in this test."

    def __init__(self):
        self.calls = 0

    async def run(self, state, query):
        self.calls += 1
        return ToolResult(tool=self.name, ok=True, chunks=[{"content": f"found it ({self.calls})"}])


class FakeBoundModel:
    def __init__(self, response_fn):
        self._response_fn = response_fn

    async def ainvoke(self, messages):
        return self._response_fn(messages)


class FakeModel:
    """A fresh instance is created by get_chat_model() on every single
    agent() call (that's real production behavior), so response_fn must
    decide what to return by inspecting the message history it's given,
    not by counting its own invocations.
    """

    def __init__(self, response_fn):
        self._response_fn = response_fn

    def bind_tools(self, tools):
        return FakeBoundModel(self._response_fn)


def _tool_message_count(messages) -> int:
    return sum(1 for m in messages if m.type == "tool")


@pytest.fixture(autouse=True)
def isolated_registry():
    saved = dict(TOOL_REGISTRY)
    TOOL_REGISTRY.clear()
    yield
    TOOL_REGISTRY.clear()
    TOOL_REGISTRY.update(saved)


@pytest.fixture(autouse=True)
def no_warmup_or_priming(monkeypatch):
    async def fake_get_notebook(notebook_id):
        return None

    async def fake_search(**kwargs):
        return []

    monkeypatch.setattr(nodes.notebook_store, "get_notebook", fake_get_notebook)
    monkeypatch.setattr(nodes.supermemory_client, "search", fake_search)


@pytest.mark.asyncio
async def test_agent_calls_tool_once_then_finalizes(monkeypatch):
    fake_tool = FakeTool()
    register(fake_tool)

    def response_fn(messages):
        if _tool_message_count(messages) == 0:
            return AIMessage(
                content="", tool_calls=[{"name": "fake_tool", "args": {"query": "test"}, "id": "c1", "type": "tool_call"}]
            )
        return AIMessage(content="Here is the answer, citing [0].")

    monkeypatch.setattr(nodes, "get_chat_model", lambda: FakeModel(response_fn))

    graph = build_graph()
    result = await graph.ainvoke({"user_id": "u1", "notebook_id": "nb1", "question": "What happened?"})

    assert fake_tool.calls == 1
    assert result["final_answer"] == "Here is the answer, citing [0]."
    assert result["citations"][0]["content"] == "found it (1)"


@pytest.mark.asyncio
async def test_agent_can_call_tool_across_multiple_rounds(monkeypatch):
    fake_tool = FakeTool()
    register(fake_tool)

    def response_fn(messages):
        count = _tool_message_count(messages)
        if count < 2:
            return AIMessage(
                content="",
                tool_calls=[{"name": "fake_tool", "args": {"query": "test"}, "id": f"c{count}", "type": "tool_call"}],
            )
        return AIMessage(content="Final answer after two rounds.")

    monkeypatch.setattr(nodes, "get_chat_model", lambda: FakeModel(response_fn))

    graph = build_graph()
    result = await graph.ainvoke({"user_id": "u1", "notebook_id": "nb1", "question": "What happened?"})

    assert fake_tool.calls == 2
    assert result["final_answer"] == "Final answer after two rounds."


@pytest.mark.asyncio
async def test_max_agent_steps_cap_is_respected(monkeypatch):
    fake_tool = FakeTool()
    register(fake_tool)

    def always_calls_tool(messages):
        count = _tool_message_count(messages)
        return AIMessage(
            content="",
            tool_calls=[{"name": "fake_tool", "args": {"query": "test"}, "id": f"c{count}", "type": "tool_call"}],
        )

    monkeypatch.setattr(nodes, "get_chat_model", lambda: FakeModel(always_calls_tool))

    graph = build_graph()
    result = await graph.ainvoke({"user_id": "u1", "notebook_id": "nb1", "question": "What happened?"})

    # agent runs MAX_AGENT_STEPS times total; the final one hits the cap
    # check and routes to finalize instead of tools, so tools only ran
    # MAX_AGENT_STEPS - 1 times.
    assert fake_tool.calls == nodes.MAX_AGENT_STEPS - 1
    assert result["agent_steps"] == nodes.MAX_AGENT_STEPS
    assert "wasn't able to finish" in result["final_answer"]


@pytest.mark.asyncio
async def test_conversation_memory_and_tool_results_reset_across_turns(monkeypatch):
    """Proves two things in one real checkpointer-backed run: (1) messages
    persist across turns on the same thread_id (conversation memory), and
    (2) tool_results/citations do NOT bleed across turns (the sentinel
    reset in hydrate)."""
    fake_tool = FakeTool()
    register(fake_tool)

    def response_fn(messages):
        # Calls the tool exactly once ever (only when no tool message exists
        # anywhere in history yet) — on turn 2, turn 1's tool message is
        # still present (that's the conversation-memory part working), so
        # this naturally answers straight away without calling the tool again.
        if _tool_message_count(messages) == 0:
            return AIMessage(
                content="", tool_calls=[{"name": "fake_tool", "args": {"query": "q1"}, "id": "t1", "type": "tool_call"}]
            )
        return AIMessage(content="answer")

    monkeypatch.setattr(nodes, "get_chat_model", lambda: FakeModel(response_fn))

    checkpointer = MemorySaver()
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "nb1:u1"}}

    result1 = await graph.ainvoke({"user_id": "u1", "notebook_id": "nb1", "question": "first question"}, config)
    assert len(result1["citations"]) == 1, "first turn should have a citation from its own tool call"

    result2 = await graph.ainvoke({"user_id": "u1", "notebook_id": "nb1", "question": "second question"}, config)

    # turn 2 calls no tool of its own (fake_tool.calls stays at 1), so its
    # citations must be empty, NOT turn 1's citation bleeding through.
    assert fake_tool.calls == 1
    assert result2["citations"] == []

    # but the conversation history (messages) must carry over across turns
    human_contents = [m.content for m in result2["messages"] if m.type == "human"]
    assert "first question" in human_contents
    assert "second question" in human_contents

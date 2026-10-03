import pytest
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.messages import AIMessage

from secondbrain.orchestrator import nodes
from secondbrain.orchestrator.graph import build_graph
from secondbrain.orchestrator.registry import TOOL_REGISTRY, register
from secondbrain.orchestrator.state import ToolResult


class FakeTool:
    name = "fake_tool"
    description = "A fake tool used only in this test."

    async def run(self, state, query):
        return ToolResult(tool=self.name, ok=True, chunks=[{"content": "found it"}])


class RecordingCallback(BaseCallbackHandler):
    def __init__(self):
        self.events = []

    def on_tool_start(self, serialized, input_str, **kwargs):
        self.events.append(("tool_start", kwargs.get("name") or (serialized or {}).get("name")))

    def on_tool_end(self, output, **kwargs):
        self.events.append(("tool_end", output))


class FakeBoundModel:
    def __init__(self, response_fn):
        self._response_fn = response_fn

    async def ainvoke(self, messages):
        return self._response_fn(messages)


class FakeModel:
    def __init__(self, response_fn):
        self._response_fn = response_fn

    def bind_tools(self, tools):
        return FakeBoundModel(self._response_fn)


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
async def test_real_tool_call_fires_on_tool_start_and_end(monkeypatch):
    """Proves the fix: a real tool call made through the `tools` node shows
    up as its own on_tool_start/on_tool_end to any callback on the graph's
    config (e.g. Langfuse), not just as one opaque 'tools node ran' block.
    """
    register(FakeTool())

    def response_fn(messages):
        tool_already_called = any(m.type == "tool" for m in messages)
        if not tool_already_called:
            return AIMessage(
                content="", tool_calls=[{"name": "fake_tool", "args": {"query": "test"}, "id": "c1", "type": "tool_call"}]
            )
        return AIMessage(content="done")

    monkeypatch.setattr(nodes, "get_chat_model", lambda: FakeModel(response_fn))

    graph = build_graph()
    recorder = RecordingCallback()

    await graph.ainvoke(
        {"user_id": "u1", "notebook_id": "nb1", "question": "What happened?"},
        {"callbacks": [recorder]},
    )

    tool_starts = [e for e in recorder.events if e[0] == "tool_start"]
    tool_ends = [e for e in recorder.events if e[0] == "tool_end"]
    assert tool_starts == [("tool_start", "fake_tool")]
    assert len(tool_ends) == 1

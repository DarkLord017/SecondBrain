import json

import pytest

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
        if self.calls < 3:
            return ToolResult(tool=self.name, ok=False, error="simulated failure")
        return ToolResult(tool=self.name, ok=True, chunks=[{"content": "found it"}])


class FakeModel:
    def __init__(self, response_fn):
        self._response_fn = response_fn

    async def ainvoke(self, prompt):
        class _Resp:
            content = self._response_fn(prompt)

        return _Resp()


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch):
    saved = dict(TOOL_REGISTRY)
    TOOL_REGISTRY.clear()
    yield
    TOOL_REGISTRY.clear()
    TOOL_REGISTRY.update(saved)


@pytest.mark.asyncio
async def test_graph_retries_failing_tool_then_finishes(monkeypatch):
    fake_tool = FakeTool()
    register(fake_tool)

    def fake_response(prompt: str) -> str:
        if "planner" in prompt.lower() or "Available tools" in prompt:
            return json.dumps([{"tool": "fake_tool", "query": "test", "wave": 0}])
        return "Here is the answer, citing [0]."

    monkeypatch.setattr(nodes, "get_chat_model", lambda: FakeModel(fake_response))

    async def fake_get_notebook(notebook_id):
        return None

    monkeypatch.setattr(nodes.notebook_store, "get_notebook", fake_get_notebook)

    async def fake_search(**kwargs):
        return []  # no warm-up hit -> falls through to the planner

    monkeypatch.setattr(nodes.supermemory_client, "search", fake_search)

    graph = build_graph()
    result = await graph.ainvoke(
        {
            "user_id": "u1",
            "notebook_id": "nb1",
            "session_id": "s1",
            "question": "What happened?",
            "tool_results": {},
            "citations": [],
            "retries": 0,
            "current_wave": 0,
        }
    )

    assert fake_tool.calls == 3  # initial attempt + 2 retries
    assert result["final_answer"] is not None
    assert result["citations"][0]["content"] == "found it"

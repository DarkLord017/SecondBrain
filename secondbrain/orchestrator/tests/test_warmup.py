import pytest

from secondbrain.config import settings
from secondbrain.orchestrator import nodes
from secondbrain.orchestrator.state import ToolResult


@pytest.mark.asyncio
async def test_warmup_seeds_tool_results_and_messages_on_high_confidence_hit(monkeypatch):
    async def fake_search(query, container_tags, limit):
        assert container_tags == ["user:u1"]
        return [{"memory": "User is studying thermodynamics", "similarity": 0.95}]

    monkeypatch.setattr(nodes.supermemory_client, "search", fake_search)

    result = await nodes.warm_up(
        {"user_id": "u1", "notebook_id": "nb1", "question": "what am I studying?", "tool_results": {}}
    )

    assert result["tool_results"]["recall"].ok is True
    assert result["tool_results"]["recall"].chunks[0]["memory"] == "User is studying thermodynamics"
    assert "messages" not in result  # no fabricated tool-call message


@pytest.mark.asyncio
async def test_warmup_no_op_below_threshold(monkeypatch):
    async def fake_search(query, container_tags, limit):
        return [{"memory": "unrelated fact", "similarity": 0.1}]

    monkeypatch.setattr(nodes.supermemory_client, "search", fake_search)

    result = await nodes.warm_up({"user_id": "u1", "notebook_id": "nb1", "question": "anything"})

    assert result == {}


@pytest.mark.asyncio
async def test_warmup_no_op_on_empty_results(monkeypatch):
    async def fake_search(query, container_tags, limit):
        return []

    monkeypatch.setattr(nodes.supermemory_client, "search", fake_search)

    result = await nodes.warm_up({"user_id": "u1", "notebook_id": "nb1", "question": "anything"})

    assert result == {}


@pytest.mark.asyncio
async def test_warmup_no_op_on_error(monkeypatch):
    async def fake_search(query, container_tags, limit):
        raise RuntimeError("supermemory down")

    monkeypatch.setattr(nodes.supermemory_client, "search", fake_search)

    result = await nodes.warm_up({"user_id": "u1", "notebook_id": "nb1", "question": "anything"})

    assert result == {}


def test_warmup_threshold_is_configured():
    assert settings.warmup_similarity_threshold == 0.85


def test_primed_context_block_empty_when_no_results():
    assert nodes._primed_context_block({"tool_results": {}}) == ""


def test_primed_context_block_includes_recall_and_finder_only():
    state = {
        "tool_results": {
            "recall": ToolResult(tool="recall", ok=True, chunks=[{"content": "likes dark mode"}]),
            "finder": ToolResult(tool="finder", ok=True, chunks=[{"content": "deadline is March 1st"}]),
            "scout": ToolResult(tool="scout", ok=True, chunks=[{"content": "irrelevant web result"}]),
        }
    }
    block = nodes._primed_context_block(state)
    assert "likes dark mode" in block
    assert "deadline is March 1st" in block
    assert "irrelevant web result" not in block  # scout isn't a primed tool


def test_primed_context_block_skips_failed_results():
    state = {"tool_results": {"recall": ToolResult(tool="recall", ok=False, error="down")}}
    assert nodes._primed_context_block(state) == ""


def test_notebook_context_line_empty_when_no_notebook():
    assert nodes._notebook_context_line({"notebook_context": {}}) == ""
    assert nodes._notebook_context_line({}) == ""


def test_notebook_context_line_includes_title():
    line = nodes._notebook_context_line({"notebook_context": {"title": "Thermodynamics 101"}})
    assert "Thermodynamics 101" in line

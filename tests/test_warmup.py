import pytest

from secondbrain.config import settings
from secondbrain.orchestrator import nodes


@pytest.mark.asyncio
async def test_warmup_skips_planner_on_high_confidence_hit(monkeypatch):
    async def fake_search(query, container_tags, limit):
        assert container_tags == ["user:u1"]
        return [{"memory": "User is studying thermodynamics", "similarity": 0.95}]

    monkeypatch.setattr(nodes.supermemory_client, "search", fake_search)

    result = await nodes.warm_up({"user_id": "u1", "notebook_id": "nb1", "question": "what am I studying?"})

    assert result["warmup_answer"] == "User is studying thermodynamics"
    assert result["tool_results"]["recall"].ok is True
    assert result["tool_results"]["recall"].chunks[0]["memory"] == "User is studying thermodynamics"


@pytest.mark.asyncio
async def test_warmup_falls_through_below_threshold(monkeypatch):
    async def fake_search(query, container_tags, limit):
        return [{"memory": "unrelated fact", "similarity": 0.1}]

    monkeypatch.setattr(nodes.supermemory_client, "search", fake_search)

    result = await nodes.warm_up({"user_id": "u1", "notebook_id": "nb1", "question": "anything"})

    assert result["warmup_answer"] is None
    assert "tool_results" not in result


@pytest.mark.asyncio
async def test_warmup_falls_through_on_empty_results(monkeypatch):
    async def fake_search(query, container_tags, limit):
        return []

    monkeypatch.setattr(nodes.supermemory_client, "search", fake_search)

    result = await nodes.warm_up({"user_id": "u1", "notebook_id": "nb1", "question": "anything"})

    assert result["warmup_answer"] is None


@pytest.mark.asyncio
async def test_warmup_falls_through_on_error(monkeypatch):
    async def fake_search(query, container_tags, limit):
        raise RuntimeError("supermemory down")

    monkeypatch.setattr(nodes.supermemory_client, "search", fake_search)

    result = await nodes.warm_up({"user_id": "u1", "notebook_id": "nb1", "question": "anything"})

    assert result["warmup_answer"] is None


def test_route_after_warmup_goes_to_writer_on_hit():
    assert nodes.route_after_warmup({"warmup_answer": "something"}) == "writer"


def test_route_after_warmup_goes_to_planner_on_miss():
    assert nodes.route_after_warmup({"warmup_answer": None}) == "planner"


def test_warmup_threshold_is_configured():
    assert settings.warmup_similarity_threshold == 0.85

import pytest

from secondbrain.tools import skeptic as skeptic_mod
from secondbrain.tools.skeptic import Skeptic


@pytest.mark.asyncio
async def test_skeptic_formats_contradictions(monkeypatch):
    async def fake_get_contradictions(notebook_id):
        return [
            {
                "a_label": "Deadline is March 1st",
                "a_summary": "From the January note.",
                "b_label": "Deadline is April 15th",
                "b_summary": "From the September note.",
            }
        ]

    monkeypatch.setattr(skeptic_mod.graph_store, "get_notebook_contradictions", fake_get_contradictions)

    result = await Skeptic().run({"notebook_id": "nb1", "user_id": "u1"}, "when is the deadline?")

    assert result.ok is True
    assert len(result.chunks) == 1
    assert result.chunks[0]["content"].startswith("CONTRADICTION:")
    assert "March 1st" in result.chunks[0]["content"]
    assert "April 15th" in result.chunks[0]["content"]


@pytest.mark.asyncio
async def test_skeptic_returns_empty_chunks_when_no_contradictions(monkeypatch):
    async def fake_get_contradictions(notebook_id):
        return []

    monkeypatch.setattr(skeptic_mod.graph_store, "get_notebook_contradictions", fake_get_contradictions)

    result = await Skeptic().run({"notebook_id": "nb1", "user_id": "u1"}, "anything")

    assert result.ok is True
    assert result.chunks == []


@pytest.mark.asyncio
async def test_skeptic_returns_failed_result_on_error(monkeypatch):
    async def fake_get_contradictions(notebook_id):
        raise RuntimeError("neo4j down")

    monkeypatch.setattr(skeptic_mod.graph_store, "get_notebook_contradictions", fake_get_contradictions)

    result = await Skeptic().run({"notebook_id": "nb1", "user_id": "u1"}, "anything")

    assert result.ok is False
    assert "neo4j down" in result.error

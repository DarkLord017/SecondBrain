import pytest

from secondbrain.tools import linker as linker_mod
from secondbrain.tools.linker import Linker

IDEAS = [
    {"id": "black-holes", "label": "Black Holes", "summary": "Regions of extreme gravity.", "related_labels": ["Event Horizon"]},
    {"id": "event-horizon", "label": "Event Horizon", "summary": "The boundary of no return.", "related_labels": ["Black Holes"]},
    {"id": "coffee", "label": "Coffee", "summary": "A brewed beverage.", "related_labels": []},
]


@pytest.mark.asyncio
async def test_linker_filters_to_query_relevant_ideas(monkeypatch):
    async def fake_get_graph(notebook_id):
        return IDEAS

    monkeypatch.setattr(linker_mod.graph_store, "get_notebook_idea_graph", fake_get_graph)

    result = await Linker().run({"notebook_id": "nb1", "user_id": "u1"}, "tell me about black holes")

    assert result.ok is True
    labels = {c["idea_id"] for c in result.chunks}
    assert "black-holes" in labels
    assert "coffee" not in labels


@pytest.mark.asyncio
async def test_linker_falls_back_to_all_ideas_when_nothing_matches(monkeypatch):
    async def fake_get_graph(notebook_id):
        return IDEAS

    monkeypatch.setattr(linker_mod.graph_store, "get_notebook_idea_graph", fake_get_graph)

    result = await Linker().run({"notebook_id": "nb1", "user_id": "u1"}, "xyzzy unrelated query")

    assert result.ok is True
    assert len(result.chunks) == len(IDEAS)


@pytest.mark.asyncio
async def test_linker_includes_related_labels_in_content(monkeypatch):
    async def fake_get_graph(notebook_id):
        return IDEAS

    monkeypatch.setattr(linker_mod.graph_store, "get_notebook_idea_graph", fake_get_graph)

    result = await Linker().run({"notebook_id": "nb1", "user_id": "u1"}, "black holes")

    black_hole_chunk = next(c for c in result.chunks if c["idea_id"] == "black-holes")
    assert "Event Horizon" in black_hole_chunk["content"]


@pytest.mark.asyncio
async def test_linker_returns_failed_result_on_error(monkeypatch):
    async def fake_get_graph(notebook_id):
        raise RuntimeError("neo4j down")

    monkeypatch.setattr(linker_mod.graph_store, "get_notebook_idea_graph", fake_get_graph)

    result = await Linker().run({"notebook_id": "nb1", "user_id": "u1"}, "anything")

    assert result.ok is False
    assert "neo4j down" in result.error

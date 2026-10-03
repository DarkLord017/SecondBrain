import pytest

from secondbrain.tools import recall as recall_mod
from secondbrain.tools.recall import Recall


@pytest.mark.asyncio
async def test_recall_searches_scoped_to_user_not_notebook(monkeypatch):
    seen = {}

    async def fake_search(query, container_tags):
        seen["container_tags"] = container_tags
        return [{"memory": "User prefers dark mode"}]

    monkeypatch.setattr(recall_mod.supermemory_client, "search", fake_search)

    result = await Recall().run({"notebook_id": "nb1", "user_id": "u1"}, "what do you know about me?")

    assert result.ok is True
    assert seen["container_tags"] == ["user:u1"]
    assert result.chunks[0]["memory"] == "User prefers dark mode"


@pytest.mark.asyncio
async def test_recall_returns_failed_result_on_error(monkeypatch):
    async def fake_search(query, container_tags):
        raise RuntimeError("supermemory down")

    monkeypatch.setattr(recall_mod.supermemory_client, "search", fake_search)

    result = await Recall().run({"notebook_id": "nb1", "user_id": "u1"}, "anything")

    assert result.ok is False
    assert "supermemory down" in result.error

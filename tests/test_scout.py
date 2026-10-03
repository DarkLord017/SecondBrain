import pytest

from secondbrain.tools import scout as scout_mod
from secondbrain.tools.scout import Scout


@pytest.mark.asyncio
async def test_scout_returns_chunks_on_success(monkeypatch):
    async def fake_search(query, max_results):
        assert max_results == scout_mod.MAX_RESULTS
        return [{"title": "T", "url": "https://example.com", "content": "some web content"}]

    monkeypatch.setattr(scout_mod.tavily_client, "search", fake_search)

    result = await Scout().run({"notebook_id": "nb1", "user_id": "u1"}, "what is a black hole?")

    assert result.ok is True
    assert result.chunks[0]["content"] == "some web content"


@pytest.mark.asyncio
async def test_scout_returns_failed_result_on_error(monkeypatch):
    async def fake_search(query, max_results):
        raise RuntimeError("tavily down")

    monkeypatch.setattr(scout_mod.tavily_client, "search", fake_search)

    result = await Scout().run({"notebook_id": "nb1", "user_id": "u1"}, "anything")

    assert result.ok is False
    assert "tavily down" in result.error

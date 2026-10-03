import fakeredis.aioredis
import pytest

from secondbrain.gateway import cache


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.mark.asyncio
async def test_exact_hash_hit_skips_similarity_lookup(redis, monkeypatch):
    called = False

    async def fake_search_cache(*args, **kwargs):
        nonlocal called
        called = True
        return None

    async def fake_write_cache_entry(*args, **kwargs):
        return None

    monkeypatch.setattr(cache.supermemory_client, "search_cache", fake_search_cache)
    monkeypatch.setattr(cache.supermemory_client, "write_cache_entry", fake_write_cache_entry)

    await cache.set_cached(redis, "nb1", "what is the deadline?", "March 1st", [], "run1", ttl=60)
    result = await cache.get_cached(redis, "nb1", "what is the deadline?", similarity_threshold=0.92)

    assert result["answer"] == "March 1st"
    assert called is False


@pytest.mark.asyncio
async def test_miss_falls_through_to_similarity(redis, monkeypatch):
    async def fake_search_cache(notebook_id, question, threshold):
        return "April 15th"

    monkeypatch.setattr(cache.supermemory_client, "search_cache", fake_search_cache)

    result = await cache.get_cached(redis, "nb1", "when is it due?", similarity_threshold=0.92)
    assert result["answer"] == "April 15th"


@pytest.mark.asyncio
async def test_full_miss_returns_none(redis, monkeypatch):
    async def fake_search_cache(*args, **kwargs):
        return None

    monkeypatch.setattr(cache.supermemory_client, "search_cache", fake_search_cache)

    result = await cache.get_cached(redis, "nb1", "unrelated question", similarity_threshold=0.92)
    assert result is None

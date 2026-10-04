import asyncio

import fakeredis.aioredis
import pytest

from secondbrain.gateway.chat_lock import acquire_run_lock, release_run_lock


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.mark.asyncio
async def test_second_acquire_waits_until_first_releases(redis, monkeypatch):
    monkeypatch.setattr("secondbrain.gateway.chat_lock.POLL_INTERVAL_SECONDS", 0.01)

    order = []

    async def holder():
        await acquire_run_lock(redis, "nb1:u1")
        order.append("first-acquired")
        await asyncio.sleep(0.05)
        order.append("first-releasing")
        await release_run_lock(redis, "nb1:u1")

    async def waiter():
        await asyncio.sleep(0.01)  # ensure it starts trying after the holder has the lock
        await acquire_run_lock(redis, "nb1:u1")
        order.append("second-acquired")

    await asyncio.gather(holder(), waiter())

    assert order == ["first-acquired", "first-releasing", "second-acquired"]


@pytest.mark.asyncio
async def test_different_threads_do_not_block_each_other(redis):
    await acquire_run_lock(redis, "nb1:u1")

    # A different thread_id (different notebook+user) must acquire immediately,
    # not wait on an unrelated thread's lock.
    await asyncio.wait_for(acquire_run_lock(redis, "nb2:u1"), timeout=0.5)

    await release_run_lock(redis, "nb1:u1")
    await release_run_lock(redis, "nb2:u1")


@pytest.mark.asyncio
async def test_release_then_reacquire_same_thread(redis):
    await acquire_run_lock(redis, "nb1:u1")
    await release_run_lock(redis, "nb1:u1")
    await asyncio.wait_for(acquire_run_lock(redis, "nb1:u1"), timeout=0.5)
    await release_run_lock(redis, "nb1:u1")

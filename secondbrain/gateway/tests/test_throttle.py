import fakeredis.aioredis
import pytest

from secondbrain.gateway.throttle import (
    ThrottleExceeded,
    check_rate_limit,
    enter_stream_slot,
    exit_stream_slot,
)


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.mark.asyncio
async def test_allows_under_limit(redis):
    for _ in range(5):
        await check_rate_limit(redis, "u1", "nb1", limit_per_min=5)


@pytest.mark.asyncio
async def test_blocks_over_limit(redis):
    for _ in range(3):
        await check_rate_limit(redis, "u1", "nb1", limit_per_min=3)
    with pytest.raises(ThrottleExceeded):
        await check_rate_limit(redis, "u1", "nb1", limit_per_min=3)


@pytest.mark.asyncio
async def test_scoped_per_user_and_notebook(redis):
    for _ in range(3):
        await check_rate_limit(redis, "u1", "nb1", limit_per_min=3)
    # different notebook for the same user should have its own budget
    await check_rate_limit(redis, "u1", "nb2", limit_per_min=3)


@pytest.mark.asyncio
async def test_concurrent_stream_cap(redis):
    await enter_stream_slot(redis, "u1", max_concurrent=1)
    with pytest.raises(ThrottleExceeded):
        await enter_stream_slot(redis, "u1", max_concurrent=1)


@pytest.mark.asyncio
async def test_concurrent_stream_cap_scoped_per_user(redis):
    await enter_stream_slot(redis, "u1", max_concurrent=1)
    # a different user should have their own independent slot budget
    await enter_stream_slot(redis, "u2", max_concurrent=1)


@pytest.mark.asyncio
async def test_exit_stream_slot_frees_capacity(redis):
    await enter_stream_slot(redis, "u1", max_concurrent=1)
    await exit_stream_slot(redis, "u1")
    await enter_stream_slot(redis, "u1", max_concurrent=1)

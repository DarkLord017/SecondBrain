import fakeredis.aioredis
import pytest

from secondbrain.gateway.spend_cap import SpendCapExceeded, reserve, settle


@pytest.fixture
def redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.mark.asyncio
async def test_reserve_under_cap(redis):
    key = await reserve(redis, "u1", "nb1", cap_usd=1.0, cost_cents=50)
    assert await redis.get(key) == "50"


@pytest.mark.asyncio
async def test_reserve_over_cap_rejected_and_not_charged(redis):
    await reserve(redis, "u1", "nb1", cap_usd=0.5, cost_cents=50)
    with pytest.raises(SpendCapExceeded):
        await reserve(redis, "u1", "nb1", cap_usd=0.5, cost_cents=50)
    key = await reserve(redis, "u1", "nb1", cap_usd=1.0, cost_cents=1)  # cheap sanity call
    assert await redis.get(key) == "51"


@pytest.mark.asyncio
async def test_settle_adjusts_delta(redis):
    key = await reserve(redis, "u1", "nb1", cap_usd=5.0, cost_cents=50)
    await settle(redis, key, reserved_cents=50, actual_cents=30)
    assert await redis.get(key) == "30"

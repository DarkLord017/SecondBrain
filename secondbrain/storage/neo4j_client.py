from contextlib import asynccontextmanager

from neo4j import AsyncDriver, AsyncGraphDatabase

from secondbrain.config import settings

_driver: AsyncDriver | None = None


def init_driver() -> AsyncDriver:
    global _driver
    _driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None


def get_driver() -> AsyncDriver:
    if _driver is None:
        raise RuntimeError("neo4j driver not initialized — call init_driver() during app startup")
    return _driver


@asynccontextmanager
async def session():
    async with get_driver().session() as s:
        yield s

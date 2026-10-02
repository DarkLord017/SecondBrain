from pathlib import Path

from psycopg_pool import AsyncConnectionPool

from secondbrain.config import settings

_pool: AsyncConnectionPool | None = None

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema.sql"


async def init_pool() -> AsyncConnectionPool:
    global _pool
    _pool = AsyncConnectionPool(settings.database_url, open=False)
    await _pool.open()
    async with _pool.connection() as conn:
        await conn.execute(SCHEMA_PATH.read_text())
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("db pool not initialized — call init_pool() during app startup")
    return _pool

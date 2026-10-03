from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from secondbrain.config import settings

_checkpointer: AsyncPostgresSaver | None = None
_cm = None


async def init_checkpointer() -> AsyncPostgresSaver:
    global _checkpointer, _cm
    _cm = AsyncPostgresSaver.from_conn_string(settings.database_url)
    _checkpointer = await _cm.__aenter__()
    await _checkpointer.setup()
    return _checkpointer


async def close_checkpointer() -> None:
    global _checkpointer, _cm
    if _cm is not None:
        await _cm.__aexit__(None, None, None)
        _checkpointer = None
        _cm = None


def get_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("checkpointer not initialized — call init_checkpointer() during app startup")
    return _checkpointer

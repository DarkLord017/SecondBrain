import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from secondbrain.auth.routes import router as auth_router
from secondbrain.chat.routes import router as chat_router
from secondbrain.chat.routes import runs_router
from secondbrain.chat.ws_routes import router as ws_router
from secondbrain.ingestion.retry_worker import run_retry_worker_forever
from secondbrain.notebooks.routes import router as notebooks_router
from secondbrain.orchestrator.checkpointer import close_checkpointer, init_checkpointer
from secondbrain.storage.db import close_pool, init_pool
from secondbrain.storage.neo4j_client import close_driver, init_driver
from secondbrain.storage.redis_client import close_redis, init_redis
from secondbrain.tools.finder import register_finder
from secondbrain.tools.linker import register_linker
from secondbrain.tools.recall import register_recall
from secondbrain.tools.scout import register_scout
from secondbrain.tools.skeptic import register_skeptic
from secondbrain.upload.routes import router as upload_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await init_pool()
    app.state.redis = init_redis()
    app.state.neo4j = init_driver()
    app.state.checkpointer = await init_checkpointer()
    register_finder()
    register_scout()
    register_recall()
    register_linker()
    register_skeptic()
    retry_worker_task = asyncio.create_task(run_retry_worker_forever())
    yield
    retry_worker_task.cancel()
    await close_checkpointer()
    await close_pool()
    await close_redis()
    await close_driver()


def create_app() -> FastAPI:
    app = FastAPI(title="SecondBrain", lifespan=lifespan)
    app.include_router(auth_router)
    app.include_router(notebooks_router)
    app.include_router(upload_router)
    app.include_router(chat_router)
    app.include_router(runs_router)
    app.include_router(ws_router)
    return app


app = create_app()

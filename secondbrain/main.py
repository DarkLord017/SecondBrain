from contextlib import asynccontextmanager

from fastapi import FastAPI

from secondbrain.auth.routes import router as auth_router
from secondbrain.chat.routes import router as chat_router
from secondbrain.chat.routes import runs_router
from secondbrain.chat.ws_routes import router as ws_router
from secondbrain.notebooks.routes import router as notebooks_router
from secondbrain.storage.db import close_pool, init_pool
from secondbrain.storage.neo4j_client import close_driver, init_driver
from secondbrain.storage.redis_client import close_redis, init_redis
from secondbrain.tools.finder import register_finder
from secondbrain.upload.routes import router as upload_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await init_pool()
    app.state.redis = init_redis()
    app.state.neo4j = init_driver()
    register_finder()
    yield
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

from fastapi import Request


def get_redis(request: Request):
    return request.app.state.redis


def get_db_pool(request: Request):
    return request.app.state.db

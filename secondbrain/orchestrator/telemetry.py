
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

from secondbrain.config import settings

_enabled = False


def init_langfuse() -> None:
    """Explicitly registers the global Langfuse client from our own
    settings. pydantic-settings reading .env does NOT mutate the real
    process environment, so the SDK's own env-var auto-config wouldn't see
    these values unless we pass them in directly here.
    """
    global _enabled
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return
    Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        base_url=settings.langfuse_base_url,
    )
    _enabled = True


def get_langfuse_callbacks() -> list:
    return [CallbackHandler()] if _enabled else []

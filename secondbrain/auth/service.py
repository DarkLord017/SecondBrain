import asyncio

from tenacity import retry, stop_after_attempt, wait_exponential

from secondbrain.auth.security import hash_password, verify_password
from secondbrain.integrations.supermemory_client import write_memory
from secondbrain.storage import graph as graph_store
from secondbrain.storage import users as users_store


class ProfileSyncError(Exception):
    """Supermemory/Neo4j profile sync failed after 3 attempts."""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4), reraise=True)
async def _sync_profile(user_id: str, email: str) -> None:
    """Writes the profile into Supermemory and Neo4j in parallel
    (asyncio.TaskGroup — waits for both, cancels the sibling if one fails),
    retried up to 3 times as one unit.
    """
    async with asyncio.TaskGroup() as tg:
        tg.create_task(
            write_memory(
                content=f"User profile: {email}",
                container_tags=[f"user:{user_id}"],
                metadata={"type": "user_profile", "email": email},
            )
        )
        tg.create_task(graph_store.create_user_node(user_id=user_id, email=email))


async def signup(email: str, password: str) -> dict:
    existing = await users_store.get_user_by_email(email)
    if existing:
        raise ValueError("email already registered")

    user = await users_store.create_user(email=email, password_hash=hash_password(password))
    user_id = str(user["id"])

    try:
        await _sync_profile(user_id, email)
        await users_store.set_profile_synced(user_id, True)
        profile_synced = True
    except Exception:
        await users_store.set_profile_synced(user_id, False)
        profile_synced = False

    return {"user_id": user_id, "email": email, "profile_synced": profile_synced}


async def login(email: str, password: str) -> dict:
    user = await users_store.get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        raise PermissionError("invalid credentials")

    user_id = str(user["id"])

    if not user["profile_synced"]:
        try:
            await _sync_profile(user_id, email)
            await users_store.set_profile_synced(user_id, True)
        except Exception as e:
            raise ProfileSyncError("profile sync failed, try again later") from e

    return {"user_id": user_id, "email": email, "profile_synced": True}

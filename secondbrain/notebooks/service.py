import asyncio

from tenacity import retry, stop_after_attempt, wait_exponential

from secondbrain.integrations.supermemory_client import write_memory
from secondbrain.storage import graph as graph_store
from secondbrain.storage import notebooks as notebooks_store


class NotebookSyncError(Exception):
    """Supermemory/Neo4j notebook sync failed after 3 attempts."""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4), reraise=True)
async def _sync_notebook(notebook_id: str, title: str, owner_user_id: str) -> None:
    """Writes the notebook into Supermemory and Neo4j in parallel
    (asyncio.TaskGroup — waits for both, cancels the sibling if one fails),
    retried up to 3 times as one unit.
    """
    async with asyncio.TaskGroup() as tg:
        tg.create_task(
            write_memory(
                content=f"Notebook created: {title}",
                container_tag=f"notebook:{notebook_id}",
                metadata={"type": "notebook_profile", "title": title, "owner_user_id": owner_user_id},
            )
        )
        tg.create_task(
            graph_store.create_notebook_node(notebook_id=notebook_id, title=title, owner_user_id=owner_user_id)
        )


async def create_notebook(owner_user_id: str, title: str) -> dict:
    nb = await notebooks_store.create_notebook(owner_user_id=owner_user_id, title=title)
    notebook_id = str(nb["id"])

    try:
        await _sync_notebook(notebook_id, title, owner_user_id)
        await notebooks_store.set_synced(notebook_id, True)
        synced = True
    except Exception:
        await notebooks_store.set_synced(notebook_id, False)
        synced = False

    return {**nb, "synced": synced}


async def get_notebook(notebook_id: str) -> dict | None:
    nb = await notebooks_store.get_notebook(notebook_id)
    if not nb:
        return None

    if not nb["synced"]:
        try:
            await _sync_notebook(notebook_id, nb["title"], str(nb["owner_user_id"]))
            await notebooks_store.set_synced(notebook_id, True)
            nb["synced"] = True
        except Exception as e:
            raise NotebookSyncError("notebook sync failed, try again later") from e

    return nb

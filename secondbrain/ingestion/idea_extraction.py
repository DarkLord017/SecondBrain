import asyncio

from secondbrain.integrations.llm import extract_ideas
from secondbrain.integrations.supermemory_client import get_document
from secondbrain.storage import graph as graph_store

POLL_ATTEMPTS = 30
POLL_INTERVAL_SECONDS = 2


async def extract_and_store_ideas(
    notebook_id: str, supermemory_document_id: str, parsed_text: str | None
) -> None:
    text = parsed_text
    if text is None:
        for _ in range(POLL_ATTEMPTS):
            doc = await get_document(supermemory_document_id)
            status = doc.get("status")
            if status == "done":
                text = doc.get("raw", "") or doc.get("summary", "")
                break
            if status == "failed":
                return
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        if not text:
            # TODO: push to a retry queue instead of dropping once a worker exists.
            return

    ideas = await extract_ideas(text)
    if ideas:
        await graph_store.merge_ideas(notebook_id=notebook_id, ideas=ideas)

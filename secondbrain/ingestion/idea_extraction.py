import asyncio

from secondbrain.integrations.llm import extract_ideas
from secondbrain.integrations.supermemory_client import get_document
from secondbrain.storage import documents as documents_store
from secondbrain.storage import graph as graph_store

POLL_ATTEMPTS = 90
POLL_INTERVAL_SECONDS = 2
MAX_TIMEOUT_RETRIES = 3


async def extract_and_store_ideas(
    document_id: str, notebook_id: str, supermemory_document_id: str, parsed_text: str | None
) -> None:
    text = parsed_text
    if text is None:
        for _ in range(POLL_ATTEMPTS):
            doc = await get_document(supermemory_document_id)
            status = doc.get("status")
            if status == "done":
                text = doc.get("content") or doc.get("raw") or doc.get("summary") or ""
                break
            if status == "failed":
                await documents_store.update_document_status(document_id, "failed")
                return
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
        else:
            retry_count = await documents_store.increment_retry_count(document_id)
            if retry_count >= MAX_TIMEOUT_RETRIES:
                await documents_store.update_document_status(document_id, "failed")
            else:
                await documents_store.update_document_status(document_id, "timeout")
            return

    await documents_store.update_document_status(document_id, "done")

    if not text:
        return  # nothing to extract ideas from, but the document itself is fine

    try:
        existing_ideas = await graph_store.get_notebook_ideas(notebook_id)
        ideas = await extract_ideas(text, existing_ideas=existing_ideas)
        if ideas:
            await graph_store.merge_ideas(notebook_id=notebook_id, ideas=ideas)
    except Exception:  # noqa: BLE001 - idea extraction is enrichment, not core to the upload succeeding
        pass

"""Completes the TODO in idea_extraction.py: when a document's status is
"timeout" (polling gave up without Supermemory ever saying done or failed),
this periodically re-attempts it. A simple in-process asyncio sweep, not a
separate task-queue service — consistent with the rest of this codebase,
which has no external worker infra. Started in main.py's lifespan.
"""

import asyncio
import logging

from secondbrain.ingestion.idea_extraction import extract_and_store_ideas
from secondbrain.storage import documents as documents_store

logger = logging.getLogger(__name__)

RETRY_SWEEP_INTERVAL_SECONDS = 120


async def retry_timed_out_documents() -> None:
    """One sweep: re-attempts extraction for every document currently
    stuck in "timeout" status. extract_and_store_ideas itself handles the
    retry-count cap, flipping a document to "failed" once MAX_TIMEOUT_RETRIES
    is hit, so this never retries the same document forever.
    """
    docs = await documents_store.list_documents_by_status("timeout")
    for doc in docs:
        try:
            await extract_and_store_ideas(
                document_id=str(doc["id"]),
                notebook_id=str(doc["notebook_id"]),
                supermemory_document_id=doc["supermemory_document_id"],
                parsed_text=None,
            )
        except Exception:
            logger.exception("retry sweep failed for document_id=%s", doc["id"])


async def run_retry_worker_forever() -> None:
    while True:
        await asyncio.sleep(RETRY_SWEEP_INTERVAL_SECONDS)
        await retry_timed_out_documents()

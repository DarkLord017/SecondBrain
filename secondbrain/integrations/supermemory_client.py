"""Client for the real Supermemory REST API (https://supermemory.ai/docs).
"""

import json
from datetime import datetime, timedelta, timezone

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from secondbrain.config import settings

_retry = retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4), reraise=True)


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.supermemory_base_url,
        headers={"Authorization": f"Bearer {settings.supermemory_api_key}"},
        timeout=30.0,
    )


@_retry
async def search(
    query: str, container_tags: list[str], limit: int = 5, search_mode: str = "hybrid"
) -> list[dict]:
    async with _client() as c:
        resp = await c.post(
            "/v4/search",
            json={
                "q": query,
                "containerTags": container_tags,
                "searchMode": search_mode,
                "limit": limit,
            },
        )
        resp.raise_for_status()
        return resp.json().get("results", [])


@_retry
async def write_memory(
    content: str,
    container_tag: str,
    metadata: dict | None = None,
    forget_after: datetime | None = None,
    forget_reason: str | None = None,
) -> dict:
    """Writes to /v4/memories — full memory pipeline (fact extraction, profile
    updates), no taskType support. Use for identity/profile content, not
    reference documents (use add_document / upload_file for those).
    """
    memory: dict = {"content": content, "metadata": metadata or {}}
    if forget_after is not None:
        memory["forgetAfter"] = forget_after.strftime("%Y-%m-%dT%H:%M:%SZ")
        if forget_reason is not None:
            memory["forgetReason"] = forget_reason

    async with _client() as c:
        resp = await c.post(
            "/v4/memories",
            json={"memories": [memory], "containerTag": container_tag},
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("memories", body)[0] if isinstance(body.get("memories"), list) else body


@_retry
async def add_document(
    content: str, container_tag: str, task_type: str = "superrag", metadata: dict | None = None
) -> dict:
    async with _client() as c:
        resp = await c.post(
            "/v3/documents",
            json={
                "content": content,
                "containerTag": container_tag,
                "taskType": task_type,
                "metadata": metadata or {},
            },
        )
        resp.raise_for_status()
        return resp.json()


@_retry
async def upload_file(
    raw: bytes,
    filename: str,
    container_tags: list[str],
    file_type: str | None = None,
    mime_type: str | None = None,
    metadata: dict | None = None,
    task_type: str = "superrag",
) -> dict:
    data = {"containerTags": json.dumps(container_tags), "taskType": task_type}
    if file_type:
        data["fileType"] = file_type
    if mime_type:
        data["mimeType"] = mime_type
    if metadata:
        data["metadata"] = json.dumps(metadata)

    async with _client() as c:
        resp = await c.post(
            "/v3/documents/file",
            data=data,
            files={"file": (filename, raw, mime_type or "application/octet-stream")},
        )
        resp.raise_for_status()
        return resp.json()


@_retry
async def get_document(document_id: str) -> dict:
    async with _client() as c:
        resp = await c.get(f"/v3/documents/{document_id}")
        resp.raise_for_status()
        return resp.json()


async def write_cache_entry(notebook_id: str, question: str, answer: str, run_id: str, ttl_seconds: int) -> None:
    await write_memory(
        content=f"Q: {question}\nA: {answer}",
        container_tag=f"cache:{notebook_id}",
        metadata={"question": question, "answer": answer, "run_id": run_id},
        forget_after=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        forget_reason="chat answer cache expiry",
    )


async def search_cache(notebook_id: str, question: str, threshold: float) -> str | None:
    results = await search(
        query=question, container_tags=[f"cache:{notebook_id}"], limit=1, search_mode="hybrid"
    )
    if not results:
        return None
    top = results[0]
    if top.get("similarity", 0) >= threshold:
        return (top.get("metadata") or {}).get("answer")
    return None

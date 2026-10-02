"""Client for the real Supermemory REST API (https://supermemory.ai/docs).

Deliberately a thin httpx wrapper (not the official SDK) so the whole
integration surface is one file — swapping vendor or adding retries/mocking
touches only this module.
"""

import json

import httpx

from secondbrain.config import settings


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.supermemory_base_url,
        headers={"Authorization": f"Bearer {settings.supermemory_api_key}"},
        timeout=30.0,
    )


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


async def write_memory(content: str, container_tags: list[str], metadata: dict | None = None) -> dict:
    async with _client() as c:
        resp = await c.post(
            "/v4/memories",
            json={"memories": [{"content": content, "metadata": metadata or {}}], "containerTags": container_tags},
        )
        resp.raise_for_status()
        body = resp.json()
        return body.get("memories", body)[0] if isinstance(body.get("memories"), list) else body


async def upload_file(
    raw: bytes,
    filename: str,
    container_tags: list[str],
    file_type: str | None = None,
    mime_type: str | None = None,
    metadata: dict | None = None,
) -> dict:
    data = {"containerTags": json.dumps(container_tags)}
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


async def get_document(document_id: str) -> dict:
    async with _client() as c:
        resp = await c.get(f"/v3/documents/{document_id}")
        resp.raise_for_status()
        return resp.json()


async def write_cache_entry(notebook_id: str, question: str, answer: str, run_id: str) -> None:
    await write_memory(
        content=f"Q: {question}\nA: {answer}",
        container_tags=[f"cache:{notebook_id}"],
        metadata={"question": question, "answer": answer, "run_id": run_id},
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

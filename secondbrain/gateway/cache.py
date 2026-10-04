import hashlib
import json

import redis.asyncio as redis

from secondbrain.integrations import supermemory_client


def cache_key(notebook_id: str, prompt: str) -> str:
    h = hashlib.sha256(f"{notebook_id}:{prompt.strip().lower()}".encode()).hexdigest()
    return f"answercache:{h}"


async def get_cached(r: redis.Redis, notebook_id: str, prompt: str, similarity_threshold: float) -> dict | None:
    """Cheap exact-hash check first, then a Supermemory similarity lookup."""
    key = cache_key(notebook_id, prompt)
    raw = await r.get(key)
    if raw:
        return json.loads(raw)

    similar_answer = await supermemory_client.search_cache(notebook_id, prompt, similarity_threshold)
    if similar_answer:
        return {"answer": similar_answer, "citations": [], "citation_flags": []}
    return None


async def set_cached(
    r: redis.Redis,
    notebook_id: str,
    prompt: str,
    answer: str,
    citations: list,
    citation_flags: list,
    run_id: str,
    ttl: int,
) -> None:
    key = cache_key(notebook_id, prompt)
    await r.set(key, json.dumps({"answer": answer, "citations": citations, "citation_flags": citation_flags}), ex=ttl)
    await supermemory_client.write_cache_entry(notebook_id, prompt, answer, run_id, ttl_seconds=ttl)

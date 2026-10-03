"""Client for the real Tavily Search API (https://docs.tavily.com)."""

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from secondbrain.config import settings

_retry = retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4), reraise=True)


@_retry
async def search(query: str, max_results: int = 3) -> list[dict]:
    async with httpx.AsyncClient(
        base_url=settings.tavily_base_url,
        headers={"Authorization": f"Bearer {settings.tavily_api_key}"},
        timeout=30.0,
    ) as c:
        resp = await c.post(
            "/search",
            json={"query": query, "max_results": max_results, "search_depth": "basic"},
        )
        resp.raise_for_status()
        return resp.json().get("results", [])

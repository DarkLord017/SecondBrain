"""Client for LlamaParse (handwriting -> markdown).
"""
import asyncio

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from secondbrain.config import settings

BASE_URL = "https://api.cloud.llamaindex.ai/api/v1/parsing"

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4), reraise=True)
async def _upload(c: httpx.AsyncClient, raw: bytes, filename: str) -> str:
    upload = await c.post("/upload", files={"file": (filename, raw)})
    upload.raise_for_status()
    return upload.json()["id"]


async def _poll_for_result(c: httpx.AsyncClient, job_id: str) -> str:
    for _ in range(60):
        status_resp = await c.get(f"/job/{job_id}")
        status_resp.raise_for_status()
        status = status_resp.json().get("status")
        if status == "SUCCESS":
            result = await c.get(f"/job/{job_id}/result/markdown")
            result.raise_for_status()
            return result.json().get("markdown", "")
        if status in ("ERROR", "FAILED"):
            raise RuntimeError(f"LlamaParse job {job_id} failed")
        await asyncio.sleep(2)

    raise TimeoutError(f"LlamaParse job {job_id} did not finish in time")


async def parse_handwritten_to_markdown(raw: bytes, filename: str) -> str:
    headers = {"Authorization": f"Bearer {settings.llamaparse_api_key}"}
    async with httpx.AsyncClient(base_url=BASE_URL, headers=headers, timeout=60.0) as c:
        job_id = await _upload(c, raw, filename)
        return await _poll_for_result(c, job_id)

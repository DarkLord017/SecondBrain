"""Client for LlamaParse (handwriting -> markdown).

NOTE: unlike the Supermemory client, this endpoint shape was NOT re-verified
against live docs this session — it follows LlamaParse's standard public
upload/job-poll convention. Confirm against https://docs.cloud.llamaindex.ai
before relying on this in anything beyond local dev.
"""

import asyncio

import httpx

from secondbrain.config import settings

BASE_URL = "https://api.cloud.llamaindex.ai/api/v1/parsing"


async def parse_handwritten_to_markdown(raw: bytes, filename: str) -> str:
    headers = {"Authorization": f"Bearer {settings.llamaparse_api_key}"}
    async with httpx.AsyncClient(base_url=BASE_URL, headers=headers, timeout=60.0) as c:
        upload = await c.post("/upload", files={"file": (filename, raw)})
        upload.raise_for_status()
        job_id = upload.json()["id"]

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

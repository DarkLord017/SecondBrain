
import asyncio
import random
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx 

from secondbrain.integrations import supermemory_client
from secondbrain.storage import documents as documents_store  
from secondbrain.storage import graph as graph_store  
from secondbrain.storage.db import close_pool, init_pool  
from secondbrain.storage.neo4j_client import close_driver, init_driver 

BASE_URL = "http://127.0.0.1:8000"


async def main() -> None:
    await init_pool()
    init_driver()

    try:
        codename = f"Fanout-{uuid.uuid4().hex[:6]}"
        marker = random.randint(100000, 999999)
        memo = (
            f"{codename} research note. The unique tracking marker for {codename} is {marker}. "
            f"{codename} conflicts with the earlier plan because it moves the budget to Q3 instead of Q1."
        )

        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
            email = f"e2e-{uuid.uuid4().hex[:8]}@example.com"
            resp = await client.post("/auth/signup", json={"email": email, "password": "correct-horse-battery"})
            assert resp.status_code == 201, resp.text
            user_id = resp.json()["user_id"]

            resp = await client.post("/notebooks", json={"user_id": user_id, "title": "E2E Fanout Notebook"})
            assert resp.status_code == 201, resp.text
            notebook_id = resp.json()["notebook_id"]

            files = {"file": ("note.txt", memo.encode(), "text/plain")}
            resp = await client.post(f"/notebooks/{notebook_id}/upload", data={"user_id": user_id}, files=files)
            assert resp.status_code == 202, resp.text
            document_id = resp.json()["document_id"]

            # Supermemory's own processing latency is quite variable in
            # practice (observed anywhere from a few seconds to several
            # minutes) — be patient rather than flaky.
            status = None
            for _ in range(100):
                resp = await client.get(f"/notebooks/{notebook_id}/documents/{document_id}")
                assert resp.status_code == 200, resp.text
                status = resp.json()["status"]
                if status in ("done", "failed", "timeout"):
                    break
                await asyncio.sleep(3)
            assert status == "done", f"document never finished processing, last status: {status}"
            print("upload -> processing: done")

        doc_row = await documents_store.get_document(document_id)
        assert doc_row is not None, "expected a documents row in Postgres"
        assert doc_row["status"] == "done", f"Postgres row status is {doc_row['status']!r}, expected done"
        assert doc_row["supermemory_document_id"], "expected a real Supermemory document id stored"
        print("Postgres: documents row present with status=done, supermemory_document_id set")

        results = await supermemory_client.search(
            query=f"tracking marker for {codename}", container_tags=[f"notebook:{notebook_id}"], limit=5
        )
        assert results, "expected Supermemory search to return the uploaded content"
        found = any(str(marker) in (r.get("content") or r.get("memory") or r.get("chunk") or "") for r in results)
        assert found, f"expected the unique marker {marker} to be findable via Supermemory search, got: {results}"
        print(f"Supermemory: content searchable, found marker {marker} in results")

        ideas = []
        for _ in range(20):
            ideas = await graph_store.get_notebook_ideas(notebook_id)
            if ideas:
                break
            await asyncio.sleep(2)
        assert ideas, f"expected at least one (:Idea) node attached to notebook {notebook_id} in Neo4j"
        print(f"Neo4j: {len(ideas)} idea(s) attached to the notebook:")
        for idea in ideas:
            print(" -", idea["label"], "|", idea["summary"])

    finally:
        await close_pool()
        await close_driver()

    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())

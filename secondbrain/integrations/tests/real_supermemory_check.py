"""Run: python secondbrain/integrations/tests/real_supermemory_check.py"""

import asyncio
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from secondbrain.config import settings  # noqa: E402
from secondbrain.integrations import supermemory_client as sm  # noqa: E402

PDF_URL = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
TEXT_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/Coffee"


async def main() -> None:
    if not settings.supermemory_api_key:
        print("SUPERMEMORY_API_KEY not set in .env -- nothing to run")
        return

    tag = f"test:supermemory-check-{int(time.time())}"
    headers = {"User-Agent": "SecondBrainSupermemoryCheck/0.1"}
    with httpx.Client(timeout=30, headers=headers, follow_redirects=True) as client:
        text = client.get(TEXT_URL).json()["extract"]
        pdf_bytes = client.get(PDF_URL).content

    mem = await sm.write_memory(content=text, container_tag=tag, metadata={"probe": True})
    assert mem.get("id"), mem
    print(f"write_memory -> {mem['id']}")

    doc = await sm.add_document(content=text, container_tag=tag, task_type="superrag")
    assert doc.get("id"), doc
    print(f"add_document -> {doc['id']} ({doc.get('status')})")

    file_doc = await sm.upload_file(pdf_bytes, filename="dummy.pdf", container_tags=[tag], mime_type="application/pdf")
    assert file_doc.get("id"), file_doc
    print(f"upload_file -> {file_doc['id']} ({file_doc.get('status')})")

    status = await sm.get_document(file_doc["id"])
    assert status.get("status") in ("queued", "extracting", "chunking", "embedding", "indexing", "done"), status
    print(f"get_document -> {status.get('status')}")

    await sm.write_cache_entry(
        notebook_id=tag, question="What is coffee?", answer="A brewed drink.", run_id="r1", ttl_seconds=3600
    )
    print("write_cache_entry -> ok")

    for _ in range(6):
        await asyncio.sleep(5)
        results = await sm.search(query="coffee", container_tags=[tag])
        if results:
            print(f"search -> {len(results)} result(s)")
            break
    else:
        raise AssertionError("search never returned results")

    answer = await sm.search_cache(notebook_id=tag, question="What is coffee?", threshold=0.5)
    assert answer, "search_cache found nothing"
    print(f"search_cache -> {answer!r}")

    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())

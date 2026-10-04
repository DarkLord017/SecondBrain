
import asyncio
import datetime
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx  # noqa: E402
import websockets  # noqa: E402

from golden_eval_set import build_eval_fixtures  # noqa: E402

from secondbrain.storage.neo4j_client import close_driver, init_driver  # noqa: E402

BASE_URL = "http://127.0.0.1:8000"
WS_BASE_URL = "ws://127.0.0.1:8000"


async def _upload_and_wait(client: httpx.AsyncClient, notebook_id: str, user_id: str, filename: str, content: str) -> None:
    files = {"file": (filename, content.encode(), "text/plain")}
    resp = await client.post(f"/notebooks/{notebook_id}/upload", data={"user_id": user_id}, files=files)
    resp.raise_for_status()
    document_id = resp.json()["document_id"]

    for _ in range(100):
        resp = await client.get(f"/notebooks/{notebook_id}/documents/{document_id}")
        status = resp.json()["status"]
        if status in ("done", "failed", "timeout"):
            break
        await asyncio.sleep(3)
    if status != "done":
        raise RuntimeError(f"{filename} never finished processing (status={status})")


async def _wait_for_ideas(notebook_id: str, min_count: int = 1, attempts: int = 20) -> None:
    """Idea-graph extraction runs *after* the document's status flips to
    done (a fire-and-forget background step), so give it its own window --
    learned the hard way earlier this session."""
    from secondbrain.storage import graph as graph_store

    for _ in range(attempts):
        ideas = await graph_store.get_notebook_ideas(notebook_id)
        if len(ideas) >= min_count:
            return
        await asyncio.sleep(2)


async def _ask_and_capture(client: httpx.AsyncClient, notebook_id: str, user_id: str, question: str) -> dict:
    resp = await client.post(f"/notebooks/{notebook_id}/chat", json={"user_id": user_id, "question": question})
    resp.raise_for_status()
    ack = resp.json()
    run_id = ack["run_id"]

    if ack.get("status") == "done":
        resp = await client.get(f"/runs/{run_id}")
        row = resp.json()
        return {"answer": row.get("final_answer") or "", "citations": [], "citation_flags": [], "error": row.get("error")}

    final_data = None
    error = None
    async with websockets.connect(f"{WS_BASE_URL}/ws/runs/{run_id}") as ws:
        async for raw in ws:
            event = json.loads(raw)
            if event["type"] == "final":
                final_data = event["data"]
                break
            if event["type"] == "error":
                error = event["data"]
                break

    if error:
        return {"answer": "", "citations": [], "citation_flags": [], "error": error}
    return {
        "answer": final_data["answer"] or "",
        "citations": final_data.get("citations", []),
        "citation_flags": final_data.get("citation_flags", []),
        "error": None,
    }


async def main() -> None:
    fixtures, items = build_eval_fixtures()
    init_driver()
    try:
        await _run(fixtures, items)
    finally:
        await close_driver()


async def _run(fixtures: dict, items: list[dict]) -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=60.0) as client:
        email = f"golden-eval-{uuid.uuid4().hex[:8]}@example.com"
        resp = await client.post("/auth/signup", json={"email": email, "password": "correct-horse-battery"})
        resp.raise_for_status()
        user_id = resp.json()["user_id"]

        resp = await client.post("/notebooks", json={"user_id": user_id, "title": fixtures["lumen_notebook_title"]})
        resp.raise_for_status()
        lumen_notebook_id = resp.json()["notebook_id"]
        print(f"seeding '{fixtures['lumen_notebook_title']}' ({lumen_notebook_id})...")
        await _upload_and_wait(client, lumen_notebook_id, user_id, "lumen_brief.txt", fixtures["lumen_doc"])

        resp = await client.post("/notebooks", json={"user_id": user_id, "title": fixtures["helios_notebook_title"]})
        resp.raise_for_status()
        helios_notebook_id = resp.json()["notebook_id"]
        print(f"seeding '{fixtures['helios_notebook_title']}' ({helios_notebook_id})...")
        await _upload_and_wait(client, helios_notebook_id, user_id, "helios_memo_a.txt", fixtures["helios_doc_a"])
        await _wait_for_ideas(helios_notebook_id, min_count=1)
        await _upload_and_wait(client, helios_notebook_id, user_id, "helios_memo_b.txt", fixtures["helios_doc_b"])
        await _wait_for_ideas(helios_notebook_id, min_count=2)

        notebook_ids = {"lumen": lumen_notebook_id, "helios": helios_notebook_id}

        print()
        print(f"running {len(items)} eval questions sequentially...")
        print()

        results = []
        for item in items:
            notebook_id = notebook_ids[item["notebook"]]
            started = datetime.datetime.now(datetime.timezone.utc)
            outcome = await _ask_and_capture(client, notebook_id, user_id, item["question"])
            elapsed = (datetime.datetime.now(datetime.timezone.utc) - started).total_seconds()

            answer_lower = outcome["answer"].lower()
            # each expected entry is either a required string, or a list of
            # alternative phrasings where at least one must appear
            missing = [
                expected
                for expected in item["expect_substrings"]
                if not any(
                    alt.lower() in answer_lower for alt in (expected if isinstance(expected, list) else [expected])
                )
            ]
            passed = not missing if item["hard"] else None
            tools_used = sorted({c.get("tool") for c in outcome["citations"] if c.get("tool")})

            results.append(
                {
                    "id": item["id"],
                    "category": item["category"],
                    "hard": item["hard"],
                    "passed": passed,
                    "missing": missing,
                    "tools_used": tools_used,
                    "citation_flags": outcome["citation_flags"],
                    "error": outcome["error"],
                    "answer": outcome["answer"],
                    "elapsed_s": round(elapsed, 1),
                }
            )

            if item["hard"]:
                tag = "PASS" if passed else "FAIL"
            else:
                tag = "INFO"
            print(f"[{tag}] {item['id']}  ({elapsed:.1f}s, tools={tools_used or 'none'})")
            if outcome["error"]:
                print(f"       error: {outcome['error'][:200]}")
            elif item["hard"] and missing:
                print(f"       missing expected text: {missing}")
                print(f"       got: {outcome['answer'][:200]}")
            elif not item["hard"]:
                print(f"       answer: {outcome['answer'][:200]}")
            if outcome["citation_flags"]:
                print(f"       citation_flags: {outcome['citation_flags']}")

        print()
        print("=" * 70)
        hard_results = [r for r in results if r["hard"]]
        hard_passed = sum(1 for r in hard_results if r["passed"])
        print(f"hard checks: {hard_passed}/{len(hard_results)} passed")
        errored = [r for r in results if r["error"]]
        if errored:
            print(f"runs that errored: {[r['id'] for r in errored]}")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

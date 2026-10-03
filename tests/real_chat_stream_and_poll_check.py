import asyncio
import json
import random
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
import websockets  

BASE_URL = "http://127.0.0.1:8000"
WS_BASE_URL = "ws://127.0.0.1:8000"


async def _setup_notebook_with_fact(client: httpx.AsyncClient) -> tuple[str, str, str, int]:
    codename = f"Stream-{uuid.uuid4().hex[:6]}"
    code = random.randint(100000, 999999)
    memo = f"{codename} briefing. The access code for {codename} is {code}."

    email = f"e2e-{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post("/auth/signup", json={"email": email, "password": "correct-horse-battery"})
    assert resp.status_code == 201, resp.text
    user_id = resp.json()["user_id"]

    resp = await client.post("/notebooks", json={"user_id": user_id, "title": "E2E Streaming Notebook"})
    assert resp.status_code == 201, resp.text
    notebook_id = resp.json()["notebook_id"]

    files = {"file": ("briefing.txt", memo.encode(), "text/plain")}
    resp = await client.post(f"/notebooks/{notebook_id}/upload", data={"user_id": user_id}, files=files)
    assert resp.status_code == 202, resp.text
    document_id = resp.json()["document_id"]

    # Supermemory's own processing latency is quite variable in practice
    # (observed anywhere from a few seconds to several minutes) — be patient
    # rather than flaky.
    for _ in range(100):
        resp = await client.get(f"/notebooks/{notebook_id}/documents/{document_id}")
        assert resp.status_code == 200, resp.text
        if resp.json()["status"] in ("done", "failed", "timeout"):
            break
        await asyncio.sleep(3)
    assert resp.json()["status"] == "done", "document never finished processing"

    return user_id, notebook_id, codename, code


async def check_streaming(client: httpx.AsyncClient) -> None:
    user_id, notebook_id, codename, code = await _setup_notebook_with_fact(client)

    resp = await client.post(
        f"/notebooks/{notebook_id}/chat",
        json={"user_id": user_id, "question": f"What is the access code for {codename}?"},
    )
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["run_id"]

    token_count = 0
    saw_status_event = False
    final_data = None

    async with websockets.connect(f"{WS_BASE_URL}/ws/runs/{run_id}") as ws:
        async for raw in ws:
            event = json.loads(raw)
            if event["type"] == "token":
                token_count += 1
            elif event["type"] == "status":
                saw_status_event = True
            elif event["type"] == "final":
                final_data = event["data"]
                break
            elif event["type"] == "error":
                raise AssertionError(f"run errored: {event['data']}")

    assert token_count > 0, "expected at least one real token event over the WebSocket"
    assert saw_status_event, "expected a 'status' event (verifying_citations) between the last token and final"
    assert final_data is not None, "WebSocket closed without ever sending a final event"
    answer = final_data["answer"] or ""
    assert str(code) in answer, f"expected access code {code} in the streamed answer, got: {answer}"

    print(f"streaming: {token_count} token event(s), status event seen, final answer: {answer}")


async def check_polling_without_websocket(client: httpx.AsyncClient) -> None:
    user_id, notebook_id, codename, code = await _setup_notebook_with_fact(client)

    resp = await client.post(
        f"/notebooks/{notebook_id}/chat",
        json={"user_id": user_id, "question": f"Tell me the access code for {codename}."},
    )
    assert resp.status_code == 202, resp.text
    run_id = resp.json()["run_id"]

    # Deliberately never open the WebSocket — the run executes server-side
    # regardless of whether any client is listening, so plain polling must
    # work as a fully independent, non-streaming retrieval path.
    final_answer = None
    for _ in range(60):
        resp = await client.get(f"/runs/{run_id}")
        assert resp.status_code == 200, resp.text
        row = resp.json()
        if row["status"] == "done":
            final_answer = row["final_answer"]
            break
        if row["status"] == "error":
            raise AssertionError(f"run errored: {row.get('error')}")
        await asyncio.sleep(2)

    assert final_answer is not None, "polling never observed the run reach status=done"
    assert str(code) in final_answer, f"expected access code {code} in the polled answer, got: {final_answer}"

    print(f"polling (no WS): final answer: {final_answer}")


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        await check_streaming(client)
        await check_polling_without_websocket(client)

    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())

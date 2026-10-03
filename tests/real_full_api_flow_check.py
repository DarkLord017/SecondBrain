
import asyncio
import random
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

BASE_URL = "http://127.0.0.1:8000"


async def _poll(client: httpx.AsyncClient, url: str, done_statuses: set[str], attempts: int, delay: float) -> dict:
    last = {}
    for _ in range(attempts):
        resp = await client.get(url)
        assert resp.status_code == 200, resp.text
        last = resp.json()
        if last["status"] in done_statuses:
            return last
        await asyncio.sleep(delay)
    raise AssertionError(f"timed out waiting on {url}, last seen: {last}")


async def main() -> None:
    codename = f"Project-{uuid.uuid4().hex[:6]}"
    secret_code = random.randint(100000, 999999)
    memo = (
        f"{codename} internal memo. The secret launch code for {codename} is {secret_code}. "
        f"Lead engineer: Dr. Amara Osei. Launch window opens 2027-03-14."
    )

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        email = f"e2e-{uuid.uuid4().hex[:8]}@example.com"
        password = "correct-horse-battery-staple"

        resp = await client.post("/auth/signup", json={"email": email, "password": password})
        assert resp.status_code == 201, resp.text
        user = resp.json()
        print("signup ok:", user["user_id"])

        resp = await client.post("/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200, resp.text
        assert resp.json()["user_id"] == user["user_id"]
        print("login ok")

        resp = await client.post("/notebooks", json={"user_id": user["user_id"], "title": "E2E Full Flow Notebook"})
        assert resp.status_code == 201, resp.text
        notebook_id = resp.json()["notebook_id"]
        print("notebook created:", notebook_id)

        resp = await client.get(f"/notebooks/{notebook_id}")
        assert resp.status_code == 200 and resp.json()["notebook_id"] == notebook_id
        print("notebook fetch ok")

        files = {"file": ("memo.txt", memo.encode(), "text/plain")}
        resp = await client.post(
            f"/notebooks/{notebook_id}/upload", data={"user_id": user["user_id"]}, files=files
        )
        assert resp.status_code == 202, resp.text
        doc = resp.json()
        print("upload accepted:", doc)

        # Supermemory's own processing latency is quite variable in practice
        # (observed anywhere from a few seconds to several minutes) — be
        # patient rather than flaky.
        doc_status = await _poll(
            client, f"/notebooks/{notebook_id}/documents/{doc['document_id']}", {"done", "failed", "timeout"}, 100, 3
        )
        assert doc_status["status"] == "done", f"document did not finish processing: {doc_status}"
        print("document processed:", doc_status["status"])

        resp = await client.post(
            f"/notebooks/{notebook_id}/chat",
            json={"user_id": user["user_id"], "question": f"What is the secret launch code for {codename}?"},
        )
        assert resp.status_code == 202, resp.text
        run = resp.json()
        print("chat queued:", run)

        run_status = await _poll(client, f"/runs/{run['run_id']}", {"done", "error"}, 60, 2)
        assert run_status["status"] == "done", f"run ended in error: {run_status.get('error')}"
        answer = run_status["final_answer"] or ""
        print("chat answer:", answer)

        assert str(secret_code) in answer, f"expected the real secret code {secret_code} in the answer, got: {answer}"

    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())

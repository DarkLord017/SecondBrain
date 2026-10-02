"""Run: python secondbrain/ingestion/tests/real_file_ingestion_check.py"""

import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from secondbrain.config import settings  # noqa: E402
from secondbrain.ingestion.llamaparse_client import parse_handwritten_to_markdown  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLES = {
    "handwritten_letter.pdf": (
        "https://upload.wikimedia.org/wikipedia/commons/c/c3/"
        "Letter_to%29_Dear_George_%28manuscript_%28IA_lettertodeargeor00garr2%29.pdf"
    ),
    "handwritten_note.jpg": "https://upload.wikimedia.org/wikipedia/commons/e/e7/Jean-Georges_Noverre_Autograph_1790.jpg",
}


async def main() -> None:
    if not settings.llamaparse_api_key:
        print("LLAMAPARSE_API_KEY not set in .env -- nothing to run")
        return

    FIXTURES_DIR.mkdir(exist_ok=True)
    headers = {"User-Agent": "SecondBrainIngestionCheck/0.1"}
    with httpx.Client(follow_redirects=True, timeout=30, headers=headers) as client:
        for name, url in SAMPLES.items():
            path = FIXTURES_DIR / name
            if not path.exists():
                path.write_bytes(client.get(url).content)

            raw = path.read_bytes()
            markdown = await parse_handwritten_to_markdown(raw, filename=name)
            assert markdown, f"expected non-empty markdown for {name}"
            print(f"{name} ({len(raw):,} bytes) -> {markdown[:200]!r}")


if __name__ == "__main__":
    asyncio.run(main())

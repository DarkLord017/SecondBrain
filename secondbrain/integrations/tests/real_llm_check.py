"""Run: python secondbrain/integrations/tests/real_llm_check.py"""

import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from secondbrain.config import settings  # noqa: E402
from secondbrain.integrations.llm import extract_ideas  # noqa: E402

ARTICLES = {
    "octopus": "https://en.wikipedia.org/api/rest_v1/page/summary/Octopus",
    "black_hole": "https://en.wikipedia.org/api/rest_v1/page/summary/Black_hole",
    "python_lang": "https://en.wikipedia.org/api/rest_v1/page/summary/Python_(programming_language)",
}


async def main() -> None:
    if not settings.openai_api_key or not settings.llm_model:
        print("OPENAI_API_KEY / LLM_MODEL not set in .env -- nothing to run")
        return

    headers = {"User-Agent": "SecondBrainLLMCheck/0.1"}
    with httpx.Client(timeout=30, headers=headers) as client:
        for name, url in ARTICLES.items():
            text = client.get(url).json().get("extract", "")
            assert text, f"no extract text fetched for {name}"

            ideas = await extract_ideas(text)
            assert ideas, f"expected at least one idea for {name}"
            for idea in ideas:
                assert {"id", "label", "summary", "related_to"} <= idea.keys()

            print(f"\n{name} ({len(text)} chars of source text) -> {len(ideas)} ideas")
            for idea in ideas:
                print(f"  - {idea['id']}: {idea['label']} — {idea['summary']}")


if __name__ == "__main__":
    asyncio.run(main())

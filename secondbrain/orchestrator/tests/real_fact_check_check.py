"""Run: python secondbrain/orchestrator/tests/real_fact_check_check.py"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from secondbrain.config import settings  # noqa: E402
from secondbrain.orchestrator.fact_check import check_citations  # noqa: E402


async def main() -> None:
    if not settings.tavily_api_key or not settings.openai_api_key or not settings.llm_model:
        print("TAVILY_API_KEY / OPENAI_API_KEY / LLM_MODEL not set in .env -- nothing to run")
        return

    citations = [{"content": "placeholder source"}]

    out_of_range = await check_citations("The capital of France is Paris [2].", citations)
    assert len(out_of_range) == 1, out_of_range
    assert out_of_range[0]["verdict"] == "missing_source"
    print("missing_source check passed:", out_of_range[0]["reason"])

    true_claim = await check_citations("The capital of France is Paris [1].", citations)
    assert true_claim == [], f"expected a true, well-known claim to pass unflagged, got: {true_claim}"
    print("supported-claim check passed: real web evidence corroborated a true claim, no flag raised")

    false_claim = await check_citations("The capital of France is Berlin [1].", citations)
    assert len(false_claim) == 1, f"expected the false claim to be flagged, got: {false_claim}"
    assert false_claim[0]["verdict"] == "unsupported"
    print("unsupported-claim check passed:", false_claim[0]["reason"])

    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())

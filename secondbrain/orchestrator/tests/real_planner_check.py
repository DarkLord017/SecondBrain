"""Run: python secondbrain/orchestrator/tests/real_planner_check.py

Live-tests the planner node against the real LLM with all 5 tool-agents
registered, to confirm it produces sensible plans (not just unit-tested
with one fake tool).
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from secondbrain.config import settings  # noqa: E402
from secondbrain.orchestrator import nodes  # noqa: E402
from secondbrain.orchestrator.registry import TOOL_REGISTRY  # noqa: E402
from secondbrain.tools.finder import register_finder  # noqa: E402
from secondbrain.tools.linker import register_linker  # noqa: E402
from secondbrain.tools.recall import register_recall  # noqa: E402
from secondbrain.tools.scout import register_scout  # noqa: E402
from secondbrain.tools.skeptic import register_skeptic  # noqa: E402

QUESTIONS = [
    "What does my note say about the deadline, and is there anything on the web about this topic?",
    "What have I told you about myself before?",
    "How do the ideas in this notebook connect to each other?",
    "Is there anything in my notes that contradicts itself?",
    "What's 2 + 2?",
]


async def main() -> None:
    if not settings.openai_api_key or not settings.llm_model:
        print("OPENAI_API_KEY / LLM_MODEL not set in .env -- nothing to run")
        return

    register_finder()
    register_scout()
    register_recall()
    register_linker()
    register_skeptic()
    print("registered tools:", list(TOOL_REGISTRY.keys()))

    for q in QUESTIONS:
        result = await nodes.planner({"question": q})
        plan = result["plan"]
        print(f"\nQ: {q}")
        print(f"  plan: {json.dumps(plan)}")
        assert plan, "planner produced an empty plan"
        assert all(s["tool"] in TOOL_REGISTRY for s in plan), "planner picked an unregistered tool"
        assert len(plan) <= nodes.MAX_PLAN_STEPS

    print("\nAll checks passed.")


if __name__ == "__main__":
    asyncio.run(main())

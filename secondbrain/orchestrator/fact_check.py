import re

from secondbrain.integrations import tavily_client
from secondbrain.integrations.llm import verify_claim

_CITATION_RE = re.compile(r"\[(\d+)\]")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _claims_by_citation(answer: str) -> dict[int, str]:
    claims: dict[int, str] = {}
    for sentence in _SENTENCE_SPLIT_RE.split(answer or ""):
        for n in _CITATION_RE.findall(sentence):
            claims.setdefault(int(n), sentence.strip())
    return claims


async def check_citations(final_answer: str, citations: list[dict]) -> list[dict]:
    """Post-hoc check: for every [n] the final answer actually cites, verify
    the claim against a fresh web search via Tavily rather than trusting the
    originally retrieved source — catches both a citation number that points
    nowhere and a citation whose claim the web doesn't actually back up.
    Cheap no-op when the answer makes no [n] claims.
    """
    flags = []
    for n, claim in _claims_by_citation(final_answer).items():
        if n < 1 or n > len(citations):
            flags.append(
                {
                    "citation": n,
                    "claim": claim,
                    "verdict": "missing_source",
                    "reason": f"answer cites [{n}] but only {len(citations)} source(s) were retrieved",
                }
            )
            continue

        try:
            evidence = await tavily_client.search(query=claim, max_results=3)
            verdict = await verify_claim(claim, evidence)
        except Exception as e:  # noqa: BLE001 - the check must never crash the graph
            flags.append({"citation": n, "claim": claim, "verdict": "uncertain", "reason": f"web check failed: {e}"})
            continue

        if not verdict["supported"]:
            flags.append({"citation": n, "claim": claim, "verdict": "unsupported", "reason": verdict["reason"]})

    return flags

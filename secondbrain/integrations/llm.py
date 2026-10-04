from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

from secondbrain.config import settings

_model: ChatOpenAI | None = None


class Idea(BaseModel):
    id: str = Field(description="kebab-case slug, unique within this response")
    label: str = Field(description="short name")
    summary: str = Field(description="one sentence")
    related_to: list[str] = Field(
        default_factory=list,
        description="ids (new or existing) that this idea relates to or builds on",
    )
    contradicts: list[str] = Field(
        default_factory=list,
        description="ids of EXISTING ideas (from the provided list) that this idea directly conflicts with",
    )


class IdeaExtraction(BaseModel):
    ideas: list[Idea] = Field(default_factory=list, max_length=8)


class CitationVerdict(BaseModel):
    supported: bool = Field(description="true only if the web evidence clearly corroborates the claim")
    reason: str = Field(description="one sentence explaining the verdict")


def get_chat_model() -> ChatOpenAI:
    global _model
    if _model is None:
        if not settings.llm_model:
            raise RuntimeError(
                "LLM_MODEL is not set — set an OpenRouter-style model slug "
                "(e.g. anthropic/claude-sonnet-4.5) in .env"
            )
        _model = ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base_url,
        )
    return _model


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4), reraise=True)
async def extract_ideas(text: str, existing_ideas: list[dict] | None = None) -> list[dict]:
    """Pull key concepts from parsed document text for the Neo4j idea graph,
    and flag when a new idea contradicts one already in the notebook (this
    is what Skeptic walks — see storage/graph.get_notebook_contradictions).

    Returns [{"id", "label", "summary", "related_to": [id, ...], "contradicts": [id, ...]}].
    """
    model = get_chat_model().with_structured_output(IdeaExtraction)
    existing_block = (
        "\n\nExisting ideas already in this notebook (reference their ids in "
        "related_to/contradicts when relevant, do not re-extract them):\n"
        + "\n".join(f"- {i['id']}: {i['label']} — {i.get('summary', '')}" for i in existing_ideas)
        if existing_ideas
        else ""
    )
    prompt = (
        "Extract at most 8 distinct key concepts/ideas from the following text. "
        "If a new idea directly conflicts with one of the existing ideas listed below "
        "(e.g. states an opposite fact, date, or conclusion), list that existing idea's id "
        "in contradicts."
        f"{existing_block}"
        f"\n\nText:\n{text[:8000]}"
    )
    result: IdeaExtraction = await model.ainvoke(prompt)
    return [idea.model_dump() for idea in result.ideas]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=4), reraise=True)
async def verify_claim(claim: str, evidence: list[dict]) -> dict:
    """Judges a cited claim from the final answer against real web search
    results (not the original notebook source — the point is independent
    corroboration, so a hallucinated or misattributed citation gets caught).
    """
    model = get_chat_model().with_structured_output(CitationVerdict)
    evidence_block = "\n".join(
        f"- {e.get('title', '')}: {(e.get('content') or '')[:500]}" for e in evidence
    ) or "(no web results found)"
    prompt = (
        "A notebook assistant made the following claim and cited a source for it.\n\n"
        "First decide what KIND of claim this is:\n"
        "1. A publicly verifiable fact — scientific, historical, encyclopedic, or general "
        "knowledge that a reasonable web search should be able to confirm (e.g. 'CVD uses "
        "precursor gases', 'water boils at 100C'). Judge these normally against the evidence: "
        "mark unsupported if the evidence contradicts the claim, or is absent for something "
        "that should be well-documented publicly.\n"
        "2. Private or source-specific information — something scoped to the user's own notes, "
        "an organization, or a private document (e.g. an internal budget figure, a specific "
        "person's role on a private project, a number from someone's personal records). The "
        "public web has no way to confirm or deny these and never will — do NOT mark these "
        "unsupported just because the search came back empty or irrelevant. Mark them supported.\n"
        "3. Not a factual claim at all — narrative or descriptive content (e.g. retelling what "
        "happens in a story, describing a character), opinion, or summary. Nothing here to "
        "verify against the web — mark supported.\n\n"
        "Watch out: a web search for a private/made-up name (e.g. a codename like 'Lumen-8246c6' "
        "or 'Project Nightingale') often returns results about a completely different, unrelated "
        "real-world thing that just happens to share part of the name (a real company, product, "
        "or person). That coincidental-match evidence is NOT relevant evidence — treat it exactly "
        "the same as finding no evidence at all (case 2 applies: do not flag).\n\n"
        "Only mark unsupported when it's genuinely case 1 AND the evidence is actually ABOUT the "
        "same specific subject as the claim, and it contradicts or fails to back it up.\n\n"
        "Worked examples:\n"
        '  Claim: "The budget for Project Lumen is $62,841 [1]." Evidence: (no web results found)\n'
        "  -> supported=true. This is case 2 (an internal project budget) — empty web evidence "
        "is EXPECTED here, not suspicious, so it is not grounds to flag it.\n"
        '  Claim: "The budget for Lumen-8246c6 is $35,241 [1]." Evidence: a budgeting app called '
        '"Lumen" with $13.1M revenue, unrelated to any "Lumen-8246c6".\n'
        "  -> supported=true. The evidence is about a different, unrelated 'Lumen' that coincidentally "
        "shares a name — not relevant evidence, so this is still case 2.\n"
        '  Claim: "Water boils at 100C at sea level [1]." Evidence: confirms 100C.\n'
        "  -> supported=true. Case 1, evidence backs it up.\n"
        '  Claim: "The capital of France is Berlin [1]." Evidence: states the capital is Paris.\n'
        "  -> supported=false. Case 1, evidence directly contradicts the claim.\n\n"
        "Now judge this one, using ONLY the web evidence below:\n\n"
        f"Claim: {claim}\n\nWeb evidence:\n{evidence_block}"
    )
    result: CitationVerdict = await model.ainvoke(prompt)
    return result.model_dump()

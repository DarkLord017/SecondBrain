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

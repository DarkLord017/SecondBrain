import json

from langchain_anthropic import ChatAnthropic

from secondbrain.config import settings

_model: ChatAnthropic | None = None


def get_chat_model() -> ChatAnthropic:
    global _model
    if _model is None:
        if not settings.anthropic_model:
            raise RuntimeError(
                "ANTHROPIC_MODEL is not set — verify the current model id against "
                "https://docs.anthropic.com/en/docs/about-claude/models and set it in .env"
            )
        _model = ChatAnthropic(
            model=settings.anthropic_model, api_key=settings.anthropic_api_key
        )
    return _model


async def extract_ideas(text: str) -> list[dict]:
    """Pull key concepts from parsed document text for the Neo4j idea graph.

    Returns [{"id": str, "label": str, "summary": str, "related_to": [id, ...]}].
    """
    model = get_chat_model()
    prompt = (
        "Extract at most 8 distinct key concepts/ideas from the following text. "
        "Respond with ONLY a JSON array, no prose, each item shaped as "
        '{"id": "<kebab-case-slug>", "label": "<short name>", "summary": "<one sentence>", '
        '"related_to": ["<id of another item in this same array that it relates to>", ...]}.'
        f"\n\nText:\n{text[:8000]}"
    )
    resp = await model.ainvoke(prompt)
    try:
        return json.loads(resp.content)
    except (json.JSONDecodeError, TypeError):
        return []

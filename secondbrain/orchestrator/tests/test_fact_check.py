import pytest

from secondbrain.orchestrator import fact_check


def test_claims_by_citation_groups_sentences_by_marker():
    answer = "The deadline is March 1st [1]. Revenue grew 12% [2]. Unrelated sentence with no citation."
    claims = fact_check._claims_by_citation(answer)
    assert claims == {
        1: "The deadline is March 1st [1].",
        2: "Revenue grew 12% [2].",
    }


def test_claims_by_citation_returns_empty_for_no_markers():
    assert fact_check._claims_by_citation("Just a plain answer with no citations.") == {}


@pytest.mark.asyncio
async def test_check_citations_is_a_noop_without_markers():
    flags = await fact_check.check_citations("No citations here.", [{"content": "irrelevant"}])
    assert flags == []


@pytest.mark.asyncio
async def test_check_citations_flags_out_of_range_citation():
    flags = await fact_check.check_citations("The deadline is March 1st [2].", [{"content": "only one source"}])
    assert len(flags) == 1
    assert flags[0]["citation"] == 2
    assert flags[0]["verdict"] == "missing_source"


@pytest.mark.asyncio
async def test_check_citations_flags_unsupported_claim(monkeypatch):
    async def fake_search(query, max_results=3):
        return [{"title": "Unrelated", "content": "nothing to do with the claim"}]

    async def fake_verify_claim(claim, evidence):
        return {"supported": False, "reason": "evidence does not mention the claim"}

    monkeypatch.setattr(fact_check.tavily_client, "search", fake_search)
    monkeypatch.setattr(fact_check, "verify_claim", fake_verify_claim)

    flags = await fact_check.check_citations("The deadline is March 1st [1].", [{"content": "source"}])
    assert len(flags) == 1
    assert flags[0]["verdict"] == "unsupported"
    assert flags[0]["reason"] == "evidence does not mention the claim"


@pytest.mark.asyncio
async def test_check_citations_passes_supported_claim(monkeypatch):
    async def fake_search(query, max_results=3):
        return [{"title": "Corroborating", "content": "the deadline is indeed March 1st"}]

    async def fake_verify_claim(claim, evidence):
        return {"supported": True, "reason": "evidence matches"}

    monkeypatch.setattr(fact_check.tavily_client, "search", fake_search)
    monkeypatch.setattr(fact_check, "verify_claim", fake_verify_claim)

    flags = await fact_check.check_citations("The deadline is March 1st [1].", [{"content": "source"}])
    assert flags == []


@pytest.mark.asyncio
async def test_check_citations_flags_uncertain_on_web_search_failure(monkeypatch):
    async def fake_search(query, max_results=3):
        raise RuntimeError("tavily is down")

    monkeypatch.setattr(fact_check.tavily_client, "search", fake_search)

    flags = await fact_check.check_citations("The deadline is March 1st [1].", [{"content": "source"}])
    assert len(flags) == 1
    assert flags[0]["verdict"] == "uncertain"

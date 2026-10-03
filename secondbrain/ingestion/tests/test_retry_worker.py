import pytest

from secondbrain.ingestion import retry_worker as mod


@pytest.mark.asyncio
async def test_sweep_retries_every_timed_out_document(monkeypatch):
    calls = []

    async def fake_list_by_status(status):
        assert status == "timeout"
        return [
            {"id": "doc1", "notebook_id": "nb1", "supermemory_document_id": "sm1"},
            {"id": "doc2", "notebook_id": "nb2", "supermemory_document_id": "sm2"},
        ]

    async def fake_extract_and_store_ideas(document_id, notebook_id, supermemory_document_id, parsed_text):
        calls.append(document_id)

    monkeypatch.setattr(mod.documents_store, "list_documents_by_status", fake_list_by_status)
    monkeypatch.setattr(mod, "extract_and_store_ideas", fake_extract_and_store_ideas)

    await mod.retry_timed_out_documents()

    assert calls == ["doc1", "doc2"]


@pytest.mark.asyncio
async def test_sweep_continues_past_individual_failures(monkeypatch):
    calls = []

    async def fake_list_by_status(status):
        return [
            {"id": "doc1", "notebook_id": "nb1", "supermemory_document_id": "sm1"},
            {"id": "doc2", "notebook_id": "nb2", "supermemory_document_id": "sm2"},
        ]

    async def fake_extract_and_store_ideas(document_id, notebook_id, supermemory_document_id, parsed_text):
        calls.append(document_id)
        if document_id == "doc1":
            raise RuntimeError("boom")

    monkeypatch.setattr(mod.documents_store, "list_documents_by_status", fake_list_by_status)
    monkeypatch.setattr(mod, "extract_and_store_ideas", fake_extract_and_store_ideas)

    await mod.retry_timed_out_documents()

    # doc1 raised, but doc2 must still have been attempted
    assert calls == ["doc1", "doc2"]


@pytest.mark.asyncio
async def test_sweep_no_op_when_nothing_timed_out(monkeypatch):
    calls = []

    async def fake_list_by_status(status):
        return []

    async def fake_extract_and_store_ideas(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(mod.documents_store, "list_documents_by_status", fake_list_by_status)
    monkeypatch.setattr(mod, "extract_and_store_ideas", fake_extract_and_store_ideas)

    await mod.retry_timed_out_documents()

    assert calls == []

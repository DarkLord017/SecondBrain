import pytest

from secondbrain.ingestion import idea_extraction as mod


@pytest.mark.asyncio
async def test_handwritten_path_marks_done_without_polling(monkeypatch):
    statuses = []

    async def fake_update_status(document_id, status):
        statuses.append((document_id, status))

    async def fake_get_notebook_ideas(notebook_id):
        return []

    async def fake_extract_ideas(text, existing_ideas=None):
        return []

    monkeypatch.setattr(mod.documents_store, "update_document_status", fake_update_status)
    monkeypatch.setattr(mod.graph_store, "get_notebook_ideas", fake_get_notebook_ideas)
    monkeypatch.setattr(mod, "extract_ideas", fake_extract_ideas)

    await mod.extract_and_store_ideas(
        document_id="doc1", notebook_id="nb1", supermemory_document_id="sm1", parsed_text="already have markdown"
    )

    assert statuses == [("doc1", "done")]


@pytest.mark.asyncio
async def test_non_handwritten_path_polls_then_marks_done(monkeypatch):
    statuses = []
    poll_calls = {"n": 0}

    async def fake_get_document(supermemory_document_id):
        poll_calls["n"] += 1
        if poll_calls["n"] < 2:
            return {"status": "extracting"}
        return {"status": "done", "content": "the real parsed text"}

    async def fake_sleep(seconds):
        return None

    async def fake_update_status(document_id, status):
        statuses.append((document_id, status))

    extracted_text = {}

    async def fake_extract_ideas(text, existing_ideas=None):
        extracted_text["value"] = text
        return []

    async def fake_get_notebook_ideas(notebook_id):
        return []

    monkeypatch.setattr(mod, "get_document", fake_get_document)
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(mod.documents_store, "update_document_status", fake_update_status)
    monkeypatch.setattr(mod.graph_store, "get_notebook_ideas", fake_get_notebook_ideas)
    monkeypatch.setattr(mod, "extract_ideas", fake_extract_ideas)

    await mod.extract_and_store_ideas(
        document_id="doc2", notebook_id="nb1", supermemory_document_id="sm2", parsed_text=None
    )

    assert statuses == [("doc2", "done")]
    assert extracted_text["value"] == "the real parsed text"


@pytest.mark.asyncio
async def test_supermemory_failed_status_marks_document_failed(monkeypatch):
    statuses = []

    async def fake_get_document(supermemory_document_id):
        return {"status": "failed"}

    async def fake_update_status(document_id, status):
        statuses.append((document_id, status))

    monkeypatch.setattr(mod, "get_document", fake_get_document)
    monkeypatch.setattr(mod.documents_store, "update_document_status", fake_update_status)

    await mod.extract_and_store_ideas(
        document_id="doc3", notebook_id="nb1", supermemory_document_id="sm3", parsed_text=None
    )

    assert statuses == [("doc3", "failed")]


@pytest.mark.asyncio
async def test_poll_timeout_marks_document_timeout_not_failed(monkeypatch):
    statuses = []

    async def fake_get_document(supermemory_document_id):
        return {"status": "extracting"}  # never finishes

    async def fake_sleep(seconds):
        return None

    async def fake_update_status(document_id, status):
        statuses.append((document_id, status))

    async def fake_increment_retry_count(document_id):
        return 1  # below MAX_TIMEOUT_RETRIES

    monkeypatch.setattr(mod, "get_document", fake_get_document)
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(mod, "POLL_ATTEMPTS", 3)
    monkeypatch.setattr(mod.documents_store, "update_document_status", fake_update_status)
    monkeypatch.setattr(mod.documents_store, "increment_retry_count", fake_increment_retry_count)

    await mod.extract_and_store_ideas(
        document_id="doc4", notebook_id="nb1", supermemory_document_id="sm4", parsed_text=None
    )

    assert statuses == [("doc4", "timeout")]


@pytest.mark.asyncio
async def test_poll_timeout_gives_up_after_max_retries(monkeypatch):
    statuses = []

    async def fake_get_document(supermemory_document_id):
        return {"status": "extracting"}

    async def fake_sleep(seconds):
        return None

    async def fake_update_status(document_id, status):
        statuses.append((document_id, status))

    async def fake_increment_retry_count(document_id):
        return mod.MAX_TIMEOUT_RETRIES  # hits the cap this time

    monkeypatch.setattr(mod, "get_document", fake_get_document)
    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(mod, "POLL_ATTEMPTS", 3)
    monkeypatch.setattr(mod.documents_store, "update_document_status", fake_update_status)
    monkeypatch.setattr(mod.documents_store, "increment_retry_count", fake_increment_retry_count)

    await mod.extract_and_store_ideas(
        document_id="doc6", notebook_id="nb1", supermemory_document_id="sm6", parsed_text=None
    )

    assert statuses == [("doc6", "failed")]


@pytest.mark.asyncio
async def test_idea_extraction_failure_does_not_undo_done_status(monkeypatch):
    """Idea extraction is enrichment — if it blows up, the document itself
    is still marked done since Supermemory successfully processed it."""
    statuses = []

    async def fake_update_status(document_id, status):
        statuses.append((document_id, status))

    async def fake_get_notebook_ideas(notebook_id):
        raise RuntimeError("neo4j down")

    monkeypatch.setattr(mod.documents_store, "update_document_status", fake_update_status)
    monkeypatch.setattr(mod.graph_store, "get_notebook_ideas", fake_get_notebook_ideas)

    await mod.extract_and_store_ideas(
        document_id="doc5", notebook_id="nb1", supermemory_document_id="sm5", parsed_text="some text"
    )

    assert statuses == [("doc5", "done")]

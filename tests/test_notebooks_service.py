import pytest

from secondbrain.notebooks import service


@pytest.mark.asyncio
async def test_create_notebook_marks_synced_true_on_success(monkeypatch):
    async def fake_write_memory(**kwargs):
        pass

    async def fake_create_notebook_node(**kwargs):
        pass

    async def fake_create_notebook(owner_user_id, title):
        return {"id": "nb1", "owner_user_id": owner_user_id, "title": title, "synced": False, "created_at": "now"}

    synced_values = []

    async def fake_set_synced(notebook_id, value):
        synced_values.append(value)

    monkeypatch.setattr(service, "write_memory", fake_write_memory)
    monkeypatch.setattr(service.graph_store, "create_notebook_node", fake_create_notebook_node)
    monkeypatch.setattr(service.notebooks_store, "create_notebook", fake_create_notebook)
    monkeypatch.setattr(service.notebooks_store, "set_synced", fake_set_synced)

    result = await service.create_notebook("u1", "Research")

    assert result["synced"] is True
    assert synced_values == [True]


@pytest.mark.asyncio
async def test_create_notebook_marks_synced_false_after_3_failed_attempts(monkeypatch):
    attempts = {"n": 0}

    async def always_fails(**kwargs):
        attempts["n"] += 1
        raise RuntimeError("supermemory down")

    async def fake_create_notebook_node(**kwargs):
        pass

    async def fake_create_notebook(owner_user_id, title):
        return {"id": "nb1", "owner_user_id": owner_user_id, "title": title, "synced": False, "created_at": "now"}

    synced_values = []

    async def fake_set_synced(notebook_id, value):
        synced_values.append(value)

    monkeypatch.setattr(service, "write_memory", always_fails)
    monkeypatch.setattr(service.graph_store, "create_notebook_node", fake_create_notebook_node)
    monkeypatch.setattr(service.notebooks_store, "create_notebook", fake_create_notebook)
    monkeypatch.setattr(service.notebooks_store, "set_synced", fake_set_synced)

    result = await service.create_notebook("u1", "Research")

    assert result["synced"] is False
    assert attempts["n"] == 3
    assert synced_values == [False]


@pytest.mark.asyncio
async def test_get_notebook_skips_resync_when_already_synced(monkeypatch):
    sync_called = False

    async def fake_write_memory(**kwargs):
        nonlocal sync_called
        sync_called = True

    async def fake_get_notebook(notebook_id):
        return {"id": "nb1", "owner_user_id": "u1", "title": "Research", "synced": True, "created_at": "now"}

    monkeypatch.setattr(service, "write_memory", fake_write_memory)
    monkeypatch.setattr(service.notebooks_store, "get_notebook", fake_get_notebook)

    result = await service.get_notebook("nb1")

    assert result["synced"] is True
    assert sync_called is False


@pytest.mark.asyncio
async def test_get_notebook_retries_and_succeeds_when_not_yet_synced(monkeypatch):
    attempts = {"n": 0}

    async def flaky_write_memory(**kwargs):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("supermemory down")

    async def fake_create_notebook_node(**kwargs):
        pass

    async def fake_get_notebook(notebook_id):
        return {"id": "nb1", "owner_user_id": "u1", "title": "Research", "synced": False, "created_at": "now"}

    synced_values = []

    async def fake_set_synced(notebook_id, value):
        synced_values.append(value)

    monkeypatch.setattr(service, "write_memory", flaky_write_memory)
    monkeypatch.setattr(service.graph_store, "create_notebook_node", fake_create_notebook_node)
    monkeypatch.setattr(service.notebooks_store, "get_notebook", fake_get_notebook)
    monkeypatch.setattr(service.notebooks_store, "set_synced", fake_set_synced)

    result = await service.get_notebook("nb1")

    assert result["synced"] is True
    assert synced_values == [True]


@pytest.mark.asyncio
async def test_get_notebook_raises_sync_error_after_3_failed_attempts(monkeypatch):
    attempts = {"n": 0}

    async def always_fails(**kwargs):
        attempts["n"] += 1
        raise RuntimeError("supermemory permanently down")

    async def fake_create_notebook_node(**kwargs):
        pass

    async def fake_get_notebook(notebook_id):
        return {"id": "nb1", "owner_user_id": "u1", "title": "Research", "synced": False, "created_at": "now"}

    monkeypatch.setattr(service, "write_memory", always_fails)
    monkeypatch.setattr(service.graph_store, "create_notebook_node", fake_create_notebook_node)
    monkeypatch.setattr(service.notebooks_store, "get_notebook", fake_get_notebook)

    with pytest.raises(service.NotebookSyncError):
        await service.get_notebook("nb1")

    assert attempts["n"] == 3


@pytest.mark.asyncio
async def test_get_notebook_returns_none_when_missing(monkeypatch):
    async def fake_get_notebook(notebook_id):
        return None

    monkeypatch.setattr(service.notebooks_store, "get_notebook", fake_get_notebook)

    result = await service.get_notebook("missing")

    assert result is None

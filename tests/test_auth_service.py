import pytest

from secondbrain.auth import service


@pytest.mark.asyncio
async def test_signup_marks_synced_true_on_success(monkeypatch):
    async def fake_write_memory(**kwargs):
        pass

    async def fake_create_user_node(**kwargs):
        pass

    async def fake_create_user(email, password_hash):
        return {"id": "u1", "email": email, "profile_synced": False, "created_at": "now"}

    synced_values = []

    async def fake_set_synced(user_id, value):
        synced_values.append(value)

    async def fake_get_user_by_email(email):
        return None

    monkeypatch.setattr(service, "write_memory", fake_write_memory)
    monkeypatch.setattr(service.graph_store, "create_user_node", fake_create_user_node)
    monkeypatch.setattr(service.users_store, "create_user", fake_create_user)
    monkeypatch.setattr(service.users_store, "set_profile_synced", fake_set_synced)
    monkeypatch.setattr(service.users_store, "get_user_by_email", fake_get_user_by_email)

    result = await service.signup("a@example.com", "pw")

    assert result["profile_synced"] is True
    assert synced_values == [True]


@pytest.mark.asyncio
async def test_signup_marks_synced_false_after_3_failed_attempts(monkeypatch):
    attempts = {"n": 0}

    async def always_fails(**kwargs):
        attempts["n"] += 1
        raise RuntimeError("supermemory down")

    async def fake_create_user_node(**kwargs):
        pass

    async def fake_create_user(email, password_hash):
        return {"id": "u1", "email": email, "profile_synced": False, "created_at": "now"}

    synced_values = []

    async def fake_set_synced(user_id, value):
        synced_values.append(value)

    async def fake_get_user_by_email(email):
        return None

    monkeypatch.setattr(service, "write_memory", always_fails)
    monkeypatch.setattr(service.graph_store, "create_user_node", fake_create_user_node)
    monkeypatch.setattr(service.users_store, "create_user", fake_create_user)
    monkeypatch.setattr(service.users_store, "set_profile_synced", fake_set_synced)
    monkeypatch.setattr(service.users_store, "get_user_by_email", fake_get_user_by_email)

    result = await service.signup("a@example.com", "pw")

    assert result["profile_synced"] is False
    assert attempts["n"] == 3
    assert synced_values == [False]


@pytest.mark.asyncio
async def test_login_skips_sync_when_already_synced(monkeypatch):
    sync_called = False

    async def fake_write_memory(**kwargs):
        nonlocal sync_called
        sync_called = True

    async def fake_get_user_by_email(email):
        return {"id": "u1", "password_hash": "hashed", "profile_synced": True}

    monkeypatch.setattr(service, "write_memory", fake_write_memory)
    monkeypatch.setattr(service.users_store, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service, "verify_password", lambda raw, hashed: True)

    result = await service.login("a@example.com", "pw")

    assert result["profile_synced"] is True
    assert sync_called is False


@pytest.mark.asyncio
async def test_login_retries_and_succeeds_when_not_yet_synced(monkeypatch):
    attempts = {"n": 0}

    async def flaky_write_memory(**kwargs):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise RuntimeError("supermemory down")

    async def fake_create_user_node(**kwargs):
        pass

    async def fake_get_user_by_email(email):
        return {"id": "u1", "password_hash": "hashed", "profile_synced": False}

    synced_values = []

    async def fake_set_synced(user_id, value):
        synced_values.append(value)

    monkeypatch.setattr(service, "write_memory", flaky_write_memory)
    monkeypatch.setattr(service.graph_store, "create_user_node", fake_create_user_node)
    monkeypatch.setattr(service.users_store, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service.users_store, "set_profile_synced", fake_set_synced)
    monkeypatch.setattr(service, "verify_password", lambda raw, hashed: True)

    result = await service.login("a@example.com", "pw")

    assert result["profile_synced"] is True
    assert synced_values == [True]


@pytest.mark.asyncio
async def test_login_raises_profile_sync_error_after_3_failed_attempts(monkeypatch):
    attempts = {"n": 0}

    async def always_fails(**kwargs):
        attempts["n"] += 1
        raise RuntimeError("supermemory permanently down")

    async def fake_create_user_node(**kwargs):
        pass

    async def fake_get_user_by_email(email):
        return {"id": "u1", "password_hash": "hashed", "profile_synced": False}

    monkeypatch.setattr(service, "write_memory", always_fails)
    monkeypatch.setattr(service.graph_store, "create_user_node", fake_create_user_node)
    monkeypatch.setattr(service.users_store, "get_user_by_email", fake_get_user_by_email)
    monkeypatch.setattr(service, "verify_password", lambda raw, hashed: True)

    with pytest.raises(service.ProfileSyncError):
        await service.login("a@example.com", "pw")

    assert attempts["n"] == 3


@pytest.mark.asyncio
async def test_login_rejects_bad_password(monkeypatch):
    async def fake_get_user_by_email(email):
        return None

    monkeypatch.setattr(service.users_store, "get_user_by_email", fake_get_user_by_email)

    with pytest.raises(PermissionError):
        await service.login("nobody@example.com", "pw")

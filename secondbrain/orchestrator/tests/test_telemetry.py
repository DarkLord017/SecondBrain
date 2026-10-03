from secondbrain.orchestrator import telemetry


def test_disabled_by_default_returns_no_callbacks(monkeypatch):
    monkeypatch.setattr(telemetry, "_enabled", False)
    assert telemetry.get_langfuse_callbacks() == []


def test_init_skips_registration_without_keys(monkeypatch):
    monkeypatch.setattr(telemetry, "_enabled", False)
    monkeypatch.setattr(telemetry.settings, "langfuse_public_key", "")
    monkeypatch.setattr(telemetry.settings, "langfuse_secret_key", "")

    telemetry.init_langfuse()

    assert telemetry._enabled is False
    assert telemetry.get_langfuse_callbacks() == []


def test_init_registers_and_enables_when_keys_present(monkeypatch):
    monkeypatch.setattr(telemetry, "_enabled", False)
    monkeypatch.setattr(telemetry.settings, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(telemetry.settings, "langfuse_secret_key", "sk-test")

    created = {}

    def fake_langfuse(public_key, secret_key, base_url):
        created["public_key"] = public_key
        created["secret_key"] = secret_key
        created["base_url"] = base_url

    monkeypatch.setattr(telemetry, "Langfuse", fake_langfuse)

    telemetry.init_langfuse()

    assert telemetry._enabled is True
    assert created["public_key"] == "pk-test"
    assert created["secret_key"] == "sk-test"

from secret_utils import ENV_REF_PLACEHOLDER, resolve_client_secret


def test_resolve_client_secret_prefers_env_ref(monkeypatch):
    monkeypatch.setenv("TENANT_X_SECRET", "abc123")
    tenant = {"client_secret_ref": "TENANT_X_SECRET", "client_secret": "legacy"}
    assert resolve_client_secret(tenant) == "abc123"


def test_resolve_client_secret_legacy_fallback():
    tenant = {"client_secret_ref": "", "client_secret": "legacy-secret"}
    assert resolve_client_secret(tenant) == "legacy-secret"


def test_resolve_client_secret_missing_returns_none(monkeypatch):
    monkeypatch.delenv("TENANT_MISSING", raising=False)
    tenant = {"client_secret_ref": "TENANT_MISSING", "client_secret": ENV_REF_PLACEHOLDER}
    assert resolve_client_secret(tenant) is None

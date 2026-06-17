import pytest
from fastapi.testclient import TestClient

from server.app import app

PROVIDER_KEYS = {
    "DEEPGRAM_API_KEY",
    "ANTHROPIC_API_KEY",
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_VOICE_ID",
    "SIMLI_API_KEY",
    "SIMLI_FACE_ID",
}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_status_reports_kb_and_readiness(client, built_index):
    resp = client.get("/tenants/lynk-and-co/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant"] == "lynk-and-co"
    assert body["kb_chunks"] > 0
    assert body["index_built"] is True
    assert set(body["missing_keys"]).issubset(PROVIDER_KEYS)
    # live_ready is exactly "KB built AND no provider keys missing".
    assert body["live_ready"] == (body["kb_chunks"] > 0 and not body["missing_keys"])


def test_status_unknown_tenant_404(client):
    assert client.get("/tenants/nope/status").status_code == 404


def test_offer_without_keys_returns_503(client, monkeypatch):
    # With provider keys missing, the live endpoint must refuse cleanly, not 500.
    import server.app as appmod

    def _missing_keys_tenant(tenant_id, env=None):
        from server.config import load_tenant

        return load_tenant(tenant_id, env={})  # empty env → all keys missing

    monkeypatch.setattr(appmod, "load_tenant", _missing_keys_tenant)
    resp = client.post("/tenants/lynk-and-co/offer", json={"sdp": "x", "type": "offer"})
    assert resp.status_code == 503
    assert "missing_keys" in resp.json()

"""Tenant #2 (aurora-ev) — proves onboarding is config + docs, no code changes."""

from fastapi.testclient import TestClient

from server.app import app
from server.config import load_tenant
from server.kb.retriever import Retriever


def test_second_tenant_ingests_and_grounds(built_aurora):
    assert built_aurora.tenant_id == "aurora-ev"
    assert built_aurora.chunks > 0

    tenant = load_tenant("aurora-ev", env={})
    retriever = Retriever.from_tenant(tenant, env={"EMBEDDER": "stub"})

    en = retriever.retrieve("What is the estimated driving range?")
    assert any(r.chunk.section.startswith("Battery") for r in en)

    ar = retriever.retrieve("ما هي مدة الضمان؟")
    assert any("الضمان" in r.chunk.section for r in ar)

    assert retriever.retrieve("What is the weather today in Tokyo?") == []


def test_tenants_are_isolated(built_index, built_aurora):
    aurora = Retriever.from_tenant(load_tenant("aurora-ev", env={}), env={"EMBEDDER": "stub"})
    # The retriever loaded aurora's own index, not Lynk's.
    assert len(aurora.store) == built_aurora.chunks
    joined = " ".join(r.chunk.text for r in aurora.retrieve("electric range and charging"))
    assert "Aurora" in joined
    assert "Lynk" not in joined
    # The two tenants persist to different index files.
    assert load_tenant("lynk-and-co", env={}).index_path != load_tenant("aurora-ev", env={}).index_path


def test_second_tenant_status(built_aurora):
    client = TestClient(app)
    body = client.get("/tenants/aurora-ev/status").json()
    assert body["tenant"] == "aurora-ev"
    assert body["name"] == "Aurora EV"
    assert body["kb_chunks"] > 0

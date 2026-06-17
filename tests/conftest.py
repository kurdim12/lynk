"""Shared fixtures. The whole suite runs offline with the stub embedder."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from server.config import load_tenant  # noqa: E402
from server.kb.ingest import ingest_tenant  # noqa: E402
from server.kb.retriever import Retriever  # noqa: E402

TENANT_ID = "lynk-and-co"
STUB_ENV = {"EMBEDDER": "stub"}


@pytest.fixture
def stub_env() -> dict:
    return dict(STUB_ENV)


@pytest.fixture
def tenant():
    # Empty env → every provider key reads as missing (the offline default).
    return load_tenant(TENANT_ID, env={})


@pytest.fixture(scope="session")
def built_index():
    """Build the KB index once with the stub embedder for the whole session."""
    return ingest_tenant(TENANT_ID, env=STUB_ENV)


@pytest.fixture(scope="session")
def built_aurora():
    """Build tenant #2's KB index (proves the multi-tenant seam)."""
    return ingest_tenant("aurora-ev", env=STUB_ENV)


@pytest.fixture
def retriever(built_index, tenant) -> Retriever:
    return Retriever.from_tenant(tenant, env=STUB_ENV)

from types import SimpleNamespace

import pytest

from server.kb.vector_store import (
    InMemoryVectorStore,
    PgVectorStore,
    make_vector_store,
    vector_store_kind,
)


def _tenant(**kb):
    return SimpleNamespace(kb=kb)


def test_kind_defaults_to_memory():
    assert vector_store_kind(_tenant()) == "memory"
    assert vector_store_kind(_tenant(vector_store="memory")) == "memory"


def test_kind_recognises_pgvector_aliases():
    for alias in ("pgvector", "postgres", "pg"):
        assert vector_store_kind(_tenant(vector_store=alias)) == "pgvector"


def test_kind_rejects_unknown():
    with pytest.raises(ValueError):
        vector_store_kind(_tenant(vector_store="redis"))


def test_make_memory_store():
    store = make_vector_store(_tenant(), embedder_name="stub", dim=8, env={})
    assert isinstance(store, InMemoryVectorStore)
    assert store.embedder == "stub" and store.dim == 8


def test_make_pgvector_requires_dsn():
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        make_vector_store(_tenant(vector_store="pgvector"), embedder_name="voyage", dim=1024, env={})


def test_make_pgvector_with_dsn_does_not_connect():
    store = make_vector_store(
        _tenant(vector_store="pgvector", pg_table="kb"),
        embedder_name="voyage",
        dim=1024,
        env={"DATABASE_URL": "postgresql://localhost/db"},
    )
    assert isinstance(store, PgVectorStore)
    assert store.table == "kb" and store.dim == 1024


def test_pgvector_conforms_to_interface():
    from server.kb.vector_store import VectorStore

    assert issubclass(PgVectorStore, VectorStore)

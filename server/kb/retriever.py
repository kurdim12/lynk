"""Retriever — embeds a query and pulls the most relevant approved passages."""

from __future__ import annotations

from typing import Mapping

from server.config import TenantConfig, embedder_name
from server.kb.embedder import Embedder, get_embedder
from server.kb.types import RetrievedChunk
from server.kb.vector_store import (
    InMemoryVectorStore,
    VectorStore,
    make_vector_store,
    vector_store_kind,
)

DEFAULT_TOP_K = 4
DEFAULT_MIN_SCORE = 0.0


class Retriever:
    """Pairs a query embedder with a vector store."""

    def __init__(
        self,
        embedder: Embedder,
        store: VectorStore,
        *,
        top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> None:
        self.embedder = embedder
        self.store = store
        self.top_k = top_k
        self.min_score = min_score

    def retrieve(
        self,
        query: str,
        *,
        top_k: int | None = None,
        min_score: float | None = None,
    ) -> list[RetrievedChunk]:
        top_k = self.top_k if top_k is None else top_k
        min_score = self.min_score if min_score is None else min_score
        query_vec = self.embedder.embed_query(query)
        results = self.store.search(query_vec, top_k=top_k)
        return [r for r in results if r.score >= min_score]

    @classmethod
    def from_tenant(cls, tenant: TenantConfig, env: Mapping[str, str] | None = None) -> "Retriever":
        """Build a retriever from a tenant's configured store + query embedder."""
        name = embedder_name(tenant, env)
        if vector_store_kind(tenant) == "memory":
            if not tenant.index_path.exists():
                raise FileNotFoundError(
                    f"No KB index for '{tenant.id}' at {tenant.index_path}. "
                    f"Run: python -m server.kb.ingest {tenant.id}"
                )
            store: VectorStore = InMemoryVectorStore.load(tenant.index_path)
            if name != store.embedder:
                # The query embedder must match the one the index was built with,
                # or vectors live in different spaces and scores are meaningless.
                raise ValueError(
                    f"Embedder mismatch: index built with '{store.embedder}' but "
                    f"'{name}' selected. Re-run ingest, or set EMBEDDER={store.embedder}."
                )
            embedder = get_embedder(name, kb_config={**tenant.kb, "dim": store.dim}, env=env)
        else:  # pgvector — the same interface, backed by Postgres
            embedder = get_embedder(name, kb_config=tenant.kb, env=env)
            store = make_vector_store(tenant, embedder_name=name, dim=embedder.dim, env=env)

        return cls(
            embedder,
            store,
            top_k=int(tenant.kb.get("top_k", DEFAULT_TOP_K)),
            min_score=float(tenant.kb.get("min_score", DEFAULT_MIN_SCORE)),
        )

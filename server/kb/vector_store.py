"""Vector stores behind one interface.

``InMemoryVectorStore`` is the event default — no database to fail on the floor;
it persists to a JSON index that ingest writes and the app/retriever load.
``PgVectorStore`` is the same interface for SaaS scale (pgvector). Swapping one
for the other is a config change, not a code change.
"""

from __future__ import annotations

import json
import math
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Sequence

from server.kb.types import Chunk, RetrievedChunk


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class VectorStore(ABC):
    """Stores embedded chunks and answers nearest-neighbour queries."""

    @abstractmethod
    def add(self, chunks: Iterable[Chunk], vectors: Iterable[Sequence[float]]) -> None:
        ...

    @abstractmethod
    def search(self, query_vector: Sequence[float], top_k: int = 4) -> list[RetrievedChunk]:
        ...

    @abstractmethod
    def __len__(self) -> int:
        ...


class InMemoryVectorStore(VectorStore):
    """In-process cosine-similarity store with JSON persistence."""

    def __init__(self, embedder: str = "stub", dim: int = 0) -> None:
        self.embedder = embedder
        self.dim = dim
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []

    def add(self, chunks: Iterable[Chunk], vectors: Iterable[Sequence[float]]) -> None:
        for chunk, vector in zip(chunks, vectors):
            self._chunks.append(chunk)
            self._vectors.append(list(vector))
            if not self.dim:
                self.dim = len(self._vectors[-1])

    def search(self, query_vector: Sequence[float], top_k: int = 4) -> list[RetrievedChunk]:
        scored = [
            RetrievedChunk(chunk=chunk, score=_cosine(query_vector, vec))
            for chunk, vec in zip(self._chunks, self._vectors)
        ]
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[: max(0, top_k)]

    def __len__(self) -> int:
        return len(self._chunks)

    # --- persistence -----------------------------------------------------

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "embedder": self.embedder,
            "dim": self.dim,
            "items": [
                {"chunk": chunk.to_dict(), "vector": vec}
                for chunk, vec in zip(self._chunks, self._vectors)
            ],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "InMemoryVectorStore":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        store = cls(embedder=data.get("embedder", "stub"), dim=data.get("dim", 0))
        for item in data.get("items", []):
            store._chunks.append(Chunk.from_dict(item["chunk"]))
            store._vectors.append([float(x) for x in item["vector"]])
        return store


class PgVectorStore(VectorStore):
    """Postgres + pgvector store — the same interface at SaaS scale.

    Implemented against psycopg 3 and the ``pgvector`` extension. It is the
    production path (KB survives restarts, scales past memory) and shares the
    exact ``add`` / ``search`` surface of the in-memory store, so the engine is
    agnostic to which one is wired. Validate against a live Postgres before
    relying on it — the offline test suite exercises the in-memory store.
    """

    def __init__(self, dsn: str, table: str = "kb_chunks", embedder: str = "voyage", dim: int = 1024) -> None:
        self.dsn = dsn
        self.table = table
        self.embedder = embedder
        self.dim = dim

    def _connect(self):  # pragma: no cover - requires a live database
        try:
            import psycopg
            from pgvector.psycopg import register_vector
        except ImportError as e:
            raise RuntimeError(
                "PgVectorStore needs `pip install 'psycopg[binary]' pgvector`."
            ) from e
        conn = psycopg.connect(self.dsn)
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(conn)
        return conn

    def ensure_schema(self) -> None:  # pragma: no cover - requires a live database
        with self._connect() as conn:
            conn.execute(
                f"CREATE TABLE IF NOT EXISTS {self.table} ("
                "id TEXT PRIMARY KEY, text TEXT, source TEXT, section TEXT, "
                f"ordinal INT, embedding vector({self.dim}))"
            )
            conn.commit()

    def add(self, chunks: Iterable[Chunk], vectors: Iterable[Sequence[float]]) -> None:  # pragma: no cover
        with self._connect() as conn:
            with conn.cursor() as cur:
                for chunk, vector in zip(chunks, vectors):
                    cur.execute(
                        f"INSERT INTO {self.table} (id, text, source, section, ordinal, embedding) "
                        "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET "
                        "text = EXCLUDED.text, embedding = EXCLUDED.embedding",
                        (chunk.id, chunk.text, chunk.source, chunk.section, chunk.ordinal, list(vector)),
                    )
            conn.commit()

    def search(self, query_vector: Sequence[float], top_k: int = 4) -> list[RetrievedChunk]:  # pragma: no cover
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT id, text, source, section, ordinal, 1 - (embedding <=> %s) AS score "
                f"FROM {self.table} ORDER BY embedding <=> %s LIMIT %s",
                (list(query_vector), list(query_vector), top_k),
            ).fetchall()
        return [
            RetrievedChunk(
                chunk=Chunk(id=r[0], text=r[1], source=r[2], section=r[3], ordinal=r[4]),
                score=float(r[5]),
            )
            for r in rows
        ]

    def __len__(self) -> int:  # pragma: no cover - requires a live database
        with self._connect() as conn:
            return int(conn.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0])

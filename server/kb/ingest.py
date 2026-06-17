"""Build a tenant's KB index from its approved docs.

    python -m server.kb.ingest lynk-and-co
    EMBEDDER=stub python -m server.kb.ingest lynk-and-co   # offline, no keys

Reads ``data/<tenant>/`` (``.md`` / ``.txt``), chunks, embeds, and writes the
vector index to ``kb_index/<tenant>.json``. Onboarding a brand is: drop a tenant
JSON + approved docs, run this. No code changes.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from server.config import TenantConfig, embedder_name, load_tenant
from server.kb.chunker import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, chunk_markdown
from server.kb.embedder import get_embedder
from server.kb.types import Chunk
from server.kb.vector_store import InMemoryVectorStore

DOC_GLOBS = ("*.md", "*.txt")


@dataclass
class IngestResult:
    tenant_id: str
    embedder: str
    documents: list[str]
    chunks: int
    index_path: Path


def _collect_docs(data_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for pattern in DOC_GLOBS:
        paths.extend(data_dir.rglob(pattern))
    return sorted(p for p in paths if p.is_file())


def build_chunks(tenant: TenantConfig) -> list[Chunk]:
    """Chunk every approved doc for a tenant."""
    chunk_size = int(tenant.kb.get("chunk_size", DEFAULT_CHUNK_SIZE))
    overlap = int(tenant.kb.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP))
    chunks: list[Chunk] = []
    for doc in _collect_docs(tenant.data_dir):
        rel = doc.relative_to(tenant.data_dir).as_posix()
        chunks.extend(
            chunk_markdown(
                doc.read_text(encoding="utf-8"),
                source=rel,
                chunk_size=chunk_size,
                chunk_overlap=overlap,
            )
        )
    return chunks


def ingest_tenant(tenant_id: str, env: Mapping[str, str] | None = None) -> IngestResult:
    tenant = load_tenant(tenant_id, env)
    if not tenant.data_dir.exists():
        raise FileNotFoundError(
            f"No approved docs directory at {tenant.data_dir}. "
            f"Add the brand's approved docs there first."
        )

    chunks = build_chunks(tenant)
    if not chunks:
        raise ValueError(
            f"No content found in {tenant.data_dir} (looked for {', '.join(DOC_GLOBS)})."
        )

    name = embedder_name(tenant, env)
    embedder = get_embedder(name, kb_config=tenant.kb, env=env)
    vectors = embedder.embed_documents([c.text for c in chunks])

    store = InMemoryVectorStore(embedder=embedder.name, dim=embedder.dim)
    store.add(chunks, vectors)
    store.save(tenant.index_path)

    docs = sorted({c.source for c in chunks})
    return IngestResult(
        tenant_id=tenant_id,
        embedder=embedder.name,
        documents=docs,
        chunks=len(chunks),
        index_path=tenant.index_path,
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: python -m server.kb.ingest <tenant-id>", file=sys.stderr)
        return 2
    tenant_id = argv[0]
    try:
        result = ingest_tenant(tenant_id)
    except (FileNotFoundError, ValueError) as e:
        print(f"ingest failed: {e}", file=sys.stderr)
        return 1

    print(f"Ingested tenant '{result.tenant_id}'")
    print(f"  embedder : {result.embedder}")
    print(f"  documents: {len(result.documents)} ({', '.join(result.documents)})")
    print(f"  chunks   : {result.chunks}")
    print(f"  index    : {result.index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

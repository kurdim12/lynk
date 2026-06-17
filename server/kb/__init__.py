"""Knowledge base: chunker · embedder · vector store · retriever · ingest.

The KB is the grounding source for the avatar — the brand's *approved* docs,
chunked and embedded so the retriever can pull the few passages relevant to a
visitor's question. Every provider sits behind a small interface, so the
in-memory event default and a SaaS-scale ``PgVectorStore`` are swappable.
"""

from server.kb.types import Chunk, RetrievedChunk

__all__ = ["Chunk", "RetrievedChunk"]

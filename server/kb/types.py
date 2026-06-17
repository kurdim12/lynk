"""Core KB data models shared across the chunker, store, and retriever."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Chunk:
    """A unit of approved content, ready to embed and retrieve."""

    id: str
    text: str
    source: str
    section: str = ""
    ordinal: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "source": self.source,
            "section": self.section,
            "ordinal": self.ordinal,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Chunk":
        return cls(
            id=d["id"],
            text=d["text"],
            source=d.get("source", ""),
            section=d.get("section", ""),
            ordinal=d.get("ordinal", 0),
            metadata=d.get("metadata", {}),
        )


@dataclass(frozen=True)
class RetrievedChunk:
    """A chunk paired with its similarity score for a given query."""

    chunk: Chunk
    score: float

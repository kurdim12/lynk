"""Embedders behind one interface.

``StubEmbedder`` is a deterministic, dependency-free, language-agnostic embedder
(word tokens + character trigrams hashed into a fixed-dim, L2-normalized vector).
It lets the whole ingest → retrieve → ground flow run and be tested offline with
no API keys, and — because trigrams overlap within a script — it produces genuine
(if lexical) relevance for both Arabic and English. Swap in ``VoyageEmbedder`` or
``OpenAIEmbedder`` for real multilingual semantic retrieval in production.
"""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from typing import Mapping

_WORD_RE = re.compile(r"\w+", re.UNICODE)
DEFAULT_DIM = 1024

# Small bilingual stoplist so common function words don't dominate similarity.
_STOPWORDS = {
    # English
    "the", "a", "an", "is", "are", "am", "be", "of", "to", "and", "or", "in",
    "on", "for", "with", "at", "by", "it", "its", "this", "that", "these",
    "those", "you", "your", "i", "me", "my", "we", "our", "do", "does", "did",
    "can", "could", "what", "which", "who", "how", "when", "where", "why",
    "tell", "about", "as", "from", "they", "their", "has", "have", "had",
    # Arabic
    "ما", "هي", "هو", "هل", "كيف", "متى", "اين", "أين", "عن", "من", "في",
    "على", "الى", "إلى", "و", "في", "مع", "هذا", "هذه", "ذلك", "التي", "الذي",
    "كم", "ماهي", "ماهو", "يتم", "هناك",
}


def _word_trigrams(word: str) -> list[str]:
    return [word[i:i + 3] for i in range(len(word) - 2)]


class Embedder(ABC):
    """Embeds documents and queries into a shared vector space."""

    name: str = "embedder"
    dim: int = DEFAULT_DIM

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def _stable_int(feature: str) -> int:
    return int.from_bytes(hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest(), "big")


class StubEmbedder(Embedder):
    """Hashing embedder — deterministic, offline, no dependencies."""

    name = "stub"

    def __init__(self, dim: int = DEFAULT_DIM) -> None:
        self.dim = dim

    def _features(self, text: str) -> dict[str, float]:
        """Weighted features: content words (1.0) + per-word trigrams (0.5).

        Per-word trigrams (not across whitespace) capture morphology — crucial
        for Arabic, where the question word and the doc form share a stem but not
        a prefix — without the generic cross-word overlap that whitespace-spanning
        trigrams would create between any two same-language strings.
        """
        features: dict[str, float] = {}
        for word in _WORD_RE.findall(text.lower()):
            if len(word) < 2 or word in _STOPWORDS:
                continue
            features[f"w:{word}"] = features.get(f"w:{word}", 0.0) + 1.0
            if len(word) >= 4:
                for tri in _word_trigrams(word):
                    features[f"t:{tri}"] = features.get(f"t:{tri}", 0.0) + 0.5
        return features

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for feature, weight in self._features(text).items():
            vec[_stable_int(feature) % self.dim] += weight
        return _l2_normalize(vec)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]


class VoyageEmbedder(Embedder):
    """Voyage AI embeddings (Anthropic's recommended multilingual partner)."""

    name = "voyage"

    def __init__(self, model: str = "voyage-3", api_key: str | None = None, dim: int = 1024) -> None:
        self.model = model
        self.api_key = api_key
        self.dim = dim

    def _client(self):
        try:
            import voyageai
        except ImportError as e:  # pragma: no cover - requires extra
            raise RuntimeError(
                "VoyageEmbedder needs `pip install voyageai` and VOYAGE_API_KEY set."
            ) from e
        return voyageai.Client(api_key=self.api_key)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - network
        result = self._client().embed(texts, model=self.model, input_type="document")
        return result.embeddings

    def embed_query(self, text: str) -> list[float]:  # pragma: no cover - network
        result = self._client().embed([text], model=self.model, input_type="query")
        return result.embeddings[0]


class OpenAIEmbedder(Embedder):
    """OpenAI embeddings — an alternative production embedder."""

    name = "openai"

    def __init__(self, model: str = "text-embedding-3-small", api_key: str | None = None, dim: int = 1536) -> None:
        self.model = model
        self.api_key = api_key
        self.dim = dim

    def embed_documents(self, texts: list[str]) -> list[list[float]]:  # pragma: no cover - network
        try:
            from openai import OpenAI
        except ImportError as e:
            raise RuntimeError(
                "OpenAIEmbedder needs `pip install openai` and OPENAI_API_KEY set."
            ) from e
        client = OpenAI(api_key=self.api_key)
        resp = client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


def get_embedder(
    name: str,
    *,
    kb_config: Mapping | None = None,
    env: Mapping[str, str] | None = None,
) -> Embedder:
    """Construct an embedder by name. ``stub`` is the offline default."""
    import os

    env = os.environ if env is None else env
    kb_config = kb_config or {}
    name = (name or "stub").lower()

    if name == "stub":
        return StubEmbedder(dim=int(kb_config.get("dim", DEFAULT_DIM)))
    if name == "voyage":
        return VoyageEmbedder(
            model=kb_config.get("model", "voyage-3"),
            api_key=env.get("VOYAGE_API_KEY"),
        )
    if name == "openai":
        return OpenAIEmbedder(
            model=kb_config.get("model", "text-embedding-3-small"),
            api_key=env.get("OPENAI_API_KEY"),
        )
    raise ValueError(f"Unknown embedder '{name}'. Use one of: stub, voyage, openai.")

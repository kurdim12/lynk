"""Pre-rendered answer cache.

A brand can pre-render answers to its common questions (FAQs). If the live
LLM/TTS path is slow or down, the kiosk can serve a cached, already-approved
answer instead of failing — the last line of the fallback chain. Keys are
normalized (case, whitespace, punctuation, language) so small phrasing
differences still hit. Pure and file-backed, so it's fully offline-testable.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

from server.config import cache_path

_TRIM_PUNCT = " \t\n؟?؛;،,.!…"


def normalize_question(question: str) -> str:
    """Normalize a question for cache keying (case/space/punctuation-insensitive)."""
    q = unicodedata.normalize("NFKC", question).lower().strip()
    q = re.sub(r"\s+", " ", q)
    return q.strip(_TRIM_PUNCT)


def _key(question: str, language: str) -> str:
    return f"{language}::{normalize_question(question)}"


@dataclass
class CachedAnswer:
    question: str
    language: str
    answer: str
    audio_path: str | None = None
    sections: list[str] | None = None


class AnswerCache:
    """A persistent map of (language, normalized question) → pre-rendered answer."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else None
        self._entries: dict[str, CachedAnswer] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, question: str, language: str) -> CachedAnswer | None:
        return self._entries.get(_key(question, language))

    def put(
        self,
        question: str,
        language: str,
        answer: str,
        *,
        audio_path: str | None = None,
        sections: list[str] | None = None,
    ) -> None:
        self._entries[_key(question, language)] = CachedAnswer(
            question=question,
            language=language,
            answer=answer,
            audio_path=audio_path,
            sections=sections,
        )

    # --- persistence -----------------------------------------------------

    def save(self, path: Path | None = None) -> None:
        path = Path(path or self.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: asdict(v) for k, v in self._entries.items()}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "AnswerCache":
        cache = cls(path)
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        cache._entries = {k: CachedAnswer(**v) for k, v in data.items()}
        return cache

    @classmethod
    def for_tenant(cls, tenant_id: str) -> "AnswerCache":
        """Load the tenant's cache, or an empty one if it hasn't been rendered."""
        path = cache_path(tenant_id)
        return cls.load(path) if path.exists() else cls(path)

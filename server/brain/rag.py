"""RAG grounding.

``RAGGrounder`` is the pure, testable core: given a visitor's utterance it
retrieves the relevant approved passages and assembles the grounded, brand-safe
system prompt for the turn. ``RAGGroundingProcessor`` is the thin Pipecat
``FrameProcessor`` that runs the grounder inside the live pipeline — it intercepts
each ``LLMContextFrame`` on its way to the LLM and refreshes the system message
with the grounding for the latest question. The Pipecat import is guarded so the
grounder (and the whole offline test path) imports without Pipecat installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from server.brain.system_prompt import build_system_prompt, detect_language, format_grounding
from server.kb.retriever import Retriever
from server.kb.types import RetrievedChunk


@dataclass
class Grounding:
    """The result of grounding one utterance."""

    query: str
    language: str
    chunks: list[RetrievedChunk]
    context_text: str
    has_context: bool
    system_prompt: str


class RAGGrounder:
    """Turns a visitor utterance into retrieved context + a grounded prompt."""

    def __init__(self, tenant, retriever: Retriever) -> None:
        self.tenant = tenant
        self.retriever = retriever

    def ground(self, query: str, language: str | None = None) -> Grounding:
        language = language or detect_language(query, self.tenant.default_language)
        chunks = self.retriever.retrieve(query)
        has_context = bool(chunks)
        context_text = format_grounding(chunks)
        system_prompt = build_system_prompt(
            self.tenant,
            grounding=context_text,
            language=language,
            has_context=has_context,
        )
        return Grounding(
            query=query,
            language=language,
            chunks=chunks,
            context_text=context_text,
            has_context=has_context,
            system_prompt=system_prompt,
        )


# --- message helpers (shared by the live processor; pure + testable) --------


def _message_text(content: Any) -> str:
    """Extract plain text from an OpenAI-style message ``content`` field."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"]
        return " ".join(p for p in parts if p)
    return ""


def last_user_text(messages: list[dict]) -> str:
    """Return the text of the most recent user message, or ``""``."""
    for message in reversed(messages):
        if message.get("role") == "user":
            return _message_text(message.get("content")).strip()
    return ""


def with_system_prompt(messages: list[dict], system_prompt: str) -> list[dict]:
    """Return ``messages`` with exactly one (grounded) system message at the front.

    Dropping prior system messages keeps the grounding fresh per turn instead of
    accumulating one block per question, while preserving the conversation turns.
    """
    rebuilt: list[dict] = [{"role": "system", "content": system_prompt}]
    rebuilt += [m for m in messages if m.get("role") != "system"]
    return rebuilt


try:  # Live pipeline only — guarded so the grounder imports without Pipecat.
    from pipecat.frames.frames import Frame, LLMContextFrame
    from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

    PIPECAT_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when Pipecat is absent
    PIPECAT_AVAILABLE = False


if PIPECAT_AVAILABLE:

    class RAGGroundingProcessor(FrameProcessor):
        """Injects per-turn grounding into the LLM context inside the pipeline.

        Place it between the user context aggregator and the LLM. On each
        ``LLMContextFrame`` it grounds the latest user utterance and rewrites the
        system message; all other frames pass through untouched.
        """

        def __init__(self, grounder: RAGGrounder, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self._grounder = grounder

        async def process_frame(self, frame: "Frame", direction: "FrameDirection") -> None:
            await super().process_frame(frame, direction)
            if isinstance(frame, LLMContextFrame):
                self._ground(frame)
            await self.push_frame(frame, direction)

        def _ground(self, frame: "LLMContextFrame") -> None:
            context = frame.context
            messages = list(context.get_messages())
            query = last_user_text(messages)
            if not query:
                return
            grounding = self._grounder.ground(query)
            context.set_messages(with_system_prompt(messages, grounding.system_prompt))

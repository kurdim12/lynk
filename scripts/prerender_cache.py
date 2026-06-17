"""Pre-render answers to a tenant's FAQs into the answer cache.

    python scripts/prerender_cache.py lynk-and-co
    EMBEDDER=stub python scripts/prerender_cache.py lynk-and-co   # offline (stub answers)

Grounds each FAQ and stores an approved answer in the cache, so the kiosk can
serve it instantly if the live LLM/TTS path is slow or down. With
ANTHROPIC_API_KEY set it renders real Claude answers under the brand-safety
contract; offline it stores a clearly-marked stub (run with a key for real text).

FAQs come from the tenant's ``faqs`` config or ``--questions-file`` (one per line).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.brain.rag import Grounding, RAGGrounder  # noqa: E402
from server.cache import AnswerCache  # noqa: E402
from server.config import cache_path, load_tenant  # noqa: E402
from server.kb.retriever import Retriever  # noqa: E402

AnswerFn = Callable[[Grounding], str]

OFFLINE_STUB = "[pre-rendered offline stub — run with ANTHROPIC_API_KEY for a real answer]"


def prerender(
    grounder: RAGGrounder,
    questions: list[str],
    answer_fn: AnswerFn,
    cache: AnswerCache,
) -> int:
    """Ground each question, render an answer, and store it. Returns the count."""
    for question in questions:
        g = grounder.ground(question)
        cache.put(
            g.query,
            g.language,
            answer_fn(g),
            sections=[r.chunk.section for r in g.chunks],
        )
    return len(questions)


def _claude_answer_fn(tenant) -> AnswerFn:
    """An answer_fn backed by Claude, under the grounded brand-safety contract."""
    import anthropic

    llm = tenant.provider("llm")
    client = anthropic.Anthropic()

    def answer(g: Grounding) -> str:
        resp = client.messages.create(
            model=llm.get("model", "claude-opus-4-8"),
            max_tokens=int(llm.get("max_tokens", 1024)),
            system=g.system_prompt,
            messages=[{"role": "user", "content": g.query}],
        )
        return next((b.text for b in resp.content if b.type == "text"), "").strip()

    return answer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pre-render FAQ answers into the cache.")
    parser.add_argument("tenant_id")
    parser.add_argument("--questions-file", help="one question per line (overrides config faqs)")
    args = parser.parse_args(argv)

    tenant = load_tenant(args.tenant_id)
    try:
        retriever = Retriever.from_tenant(tenant)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    if args.questions_file:
        questions = [q.strip() for q in Path(args.questions_file).read_text("utf-8").splitlines() if q.strip()]
    else:
        questions = list(tenant.raw.get("faqs", []))
    if not questions:
        print("No FAQs to pre-render (add `faqs` to the tenant config or pass --questions-file).", file=sys.stderr)
        return 1

    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            answer_fn = _claude_answer_fn(tenant)
            mode = "claude"
        except ImportError:
            answer_fn = lambda g: OFFLINE_STUB  # noqa: E731
            mode = "stub (anthropic not installed)"
    else:
        answer_fn = lambda g: OFFLINE_STUB  # noqa: E731
        mode = "stub (no ANTHROPIC_API_KEY)"

    cache = AnswerCache(cache_path(args.tenant_id))
    count = prerender(RAGGrounder(tenant, retriever), questions, answer_fn, cache)
    cache.save()
    print(f"Pre-rendered {count} answer(s) for '{args.tenant_id}' [{mode}] -> {cache.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

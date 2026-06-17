"""Offline demo of the KB brain — no provider keys required.

    EMBEDDER=stub python -m server.kb.ingest lynk-and-co
    EMBEDDER=stub python scripts/demo_kb.py

Asks Arabic + English questions plus an off-topic one, and for each shows the
retrieved approved passages and how the grounded, brand-safe prompt is built —
including the safe "I don't have that" path when nothing relevant is found.

If ANTHROPIC_API_KEY is set and the `anthropic` package is installed, it also
generates the avatar's actual spoken answer with Claude.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.brain.rag import Grounding, RAGGrounder  # noqa: E402
from server.config import load_tenant  # noqa: E402
from server.kb.retriever import Retriever  # noqa: E402

TENANT_ID = "lynk-and-co"

QUESTIONS = [
    "What is the electric driving range of the 01?",
    "ما هي مدة الضمان؟",
    "How can I book a test drive?",
    "كيف يتم شحن السيارة؟",
    "What is the weather today in Tokyo?",  # off-topic → safe refusal
]


def _print_grounding(g: Grounding) -> None:
    flag = "🇸🇦 AR" if g.language == "ar" else "🇬🇧 EN"
    print(f"\n{'=' * 78}\n[{flag}] {g.query}")
    if g.has_context:
        print(f"  grounded on {len(g.chunks)} approved passage(s):")
        for rc in g.chunks:
            print(f"    · {rc.score:.3f}  {rc.chunk.section or rc.chunk.id}")
    else:
        print("  no approved knowledge matched → avatar will safely decline")


def _maybe_answer(g: Grounding, tenant) -> None:
    """Generate the real spoken answer with Claude, if keys + SDK are present."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return
    try:
        import anthropic
    except ImportError:
        return
    llm = tenant.provider("llm")
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=llm.get("model", "claude-opus-4-8"),
        max_tokens=int(llm.get("max_tokens", 1024)),
        system=g.system_prompt,
        messages=[{"role": "user", "content": g.query}],
    )
    answer = next((b.text for b in resp.content if b.type == "text"), "")
    print(f"  💬 {answer.strip()}")


def main() -> int:
    tenant = load_tenant(TENANT_ID)
    try:
        retriever = Retriever.from_tenant(tenant)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    print(f"Tenant: {tenant.name}  ·  languages: {', '.join(tenant.languages)}")
    print(f"Embedder: {retriever.embedder.name}  ·  KB chunks: {len(retriever.store)}")
    print(f"top_k={retriever.top_k}  min_score={retriever.min_score}")

    grounder = RAGGrounder(tenant, retriever)
    for question in QUESTIONS:
        g = grounder.ground(question)
        _print_grounding(g)
        _maybe_answer(g, tenant)

    print(f"\n{'=' * 78}")
    print("System prompt for the first question (the brand-safety contract):\n")
    print(grounder.ground(QUESTIONS[0]).system_prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

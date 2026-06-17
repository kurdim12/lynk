"""Onboard a new brand (tenant) — no code changes required.

    python scripts/onboard_tenant.py acme-motors --name "Acme Motors" --languages ar,en

Scaffolds ``server/tenants/<id>.json`` (provider models, persona, KB settings,
per-tenant voice/face env refs) and a placeholder ``server/data/<id>/`` doc. Then:
replace the placeholder with the brand's approved docs and run
``python -m server.kb.ingest <id>``. That's the whole onboarding flow.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.config import DATA_DIR, TENANTS_DIR  # noqa: E402


def _env_suffix(tenant_id: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", tenant_id.upper()).strip("_")


def tenant_template(tenant_id: str, name: str, languages: list[str]) -> dict:
    """A complete, ready-to-edit tenant config. Voice/face are per-tenant; the
    provider API keys are shared across tenants in one deployment."""
    suffix = _env_suffix(tenant_id)
    return {
        "id": tenant_id,
        "name": name,
        "persona": {
            "name": "Specialist",
            "role": "digital product specialist",
            "style": "Warm, concise, and professional. You are speaking out loud "
            "at a showroom kiosk, so keep answers short and natural — no markdown.",
        },
        "languages": languages,
        "default_language": languages[0],
        "providers": {
            "stt": {
                "provider": "deepgram",
                "model": "nova-2-general",
                "language": "multi",
                "api_key": "ENV:DEEPGRAM_API_KEY",
            },
            "llm": {
                "provider": "anthropic",
                "model": "claude-opus-4-8",
                "max_tokens": 1024,
                "api_key": "ENV:ANTHROPIC_API_KEY",
            },
            "tts": {
                "provider": "elevenlabs",
                "model": "eleven_turbo_v2_5",
                "voice_id": f"ENV:ELEVENLABS_VOICE_ID_{suffix}",
                "api_key": "ENV:ELEVENLABS_API_KEY",
            },
            "avatar": {
                "provider": "simli",
                "face_id": f"ENV:SIMLI_FACE_ID_{suffix}",
                "api_key": "ENV:SIMLI_API_KEY",
            },
        },
        "kb": {
            "embedder": "voyage",
            "vector_store": "memory",
            "chunk_size": 800,
            "chunk_overlap": 150,
            "top_k": 4,
            "min_score": 0.12,
        },
        "brand_safety": {
            "topics_allowed": ["the brand's products and services as documented"],
            "refusal_en": f"I don't have that in my approved information yet, but I "
            f"can help with what I do know or connect you with a {name} specialist.",
            "refusal_ar": "هذه المعلومة غير متوفرة لدي ضمن المصادر المعتمدة حالياً، "
            "لكن يمكنني مساعدتك بما لدي أو توصيلك بأحد المختصين.",
        },
    }


def _placeholder_doc(name: str) -> str:
    return (
        f"# {name} — Product Information (PLACEHOLDER)\n\n"
        "> ⚠️ Replace this file with the brand's APPROVED docs before live use. "
        "The avatar says only what is written in these files.\n\n"
        "## Overview (English)\n\n"
        f"Describe {name}'s product here, in the brand's approved wording.\n\n"
        "## نظرة عامة (Arabic)\n\n"
        "اكتب هنا وصف المنتج بصياغة العلامة التجارية المعتمدة.\n"
    )


def scaffold_tenant(
    tenant_id: str,
    name: str,
    languages: list[str],
    *,
    tenants_dir: Path = TENANTS_DIR,
    data_dir: Path = DATA_DIR,
    force: bool = False,
) -> tuple[Path, Path]:
    """Write the tenant config + a placeholder doc. Returns their paths."""
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", tenant_id):
        raise ValueError("tenant id must be lowercase letters, digits, and hyphens")

    json_path = Path(tenants_dir) / f"{tenant_id}.json"
    doc_path = Path(data_dir) / tenant_id / "vehicle-info.md"
    if not force and (json_path.exists() or doc_path.exists()):
        raise FileExistsError(f"Tenant '{tenant_id}' already exists. Use --force to overwrite.")

    json_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(tenant_template(tenant_id, name, languages), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    doc_path.write_text(_placeholder_doc(name), encoding="utf-8")
    return json_path, doc_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scaffold a new tenant (brand).")
    parser.add_argument("tenant_id", help="lowercase slug, e.g. acme-motors")
    parser.add_argument("--name", help="display name (default: derived from id)")
    parser.add_argument("--languages", default="ar,en", help="comma-separated, e.g. ar,en")
    parser.add_argument("--force", action="store_true", help="overwrite if it exists")
    args = parser.parse_args(argv)

    name = args.name or args.tenant_id.replace("-", " ").title()
    languages = [s.strip() for s in args.languages.split(",") if s.strip()]
    try:
        json_path, doc_path = scaffold_tenant(args.tenant_id, name, languages, force=args.force)
    except (ValueError, FileExistsError) as e:
        print(f"onboard failed: {e}", file=sys.stderr)
        return 1

    print(f"Scaffolded tenant '{args.tenant_id}' ({name})")
    print(f"  config: {json_path}")
    print(f"  docs  : {doc_path}")
    print("\nNext:")
    print(f"  1. Replace {doc_path} with the brand's APPROVED docs")
    print(f"  2. Set the per-tenant voice/face env vars referenced in {json_path.name}")
    print(f"  3. Build the KB:  python -m server.kb.ingest {args.tenant_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

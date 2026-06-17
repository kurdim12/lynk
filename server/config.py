"""Environment + tenant configuration.

A brand is one JSON file in ``tenants/`` plus its approved docs in
``data/<tenant>/``. Secrets never live in the JSON: any string of the form
``"ENV:VAR_NAME"`` is resolved from the process environment at load time. This
keeps tenant config files safe to commit while still pointing at per-deployment
credentials.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

SERVER_DIR = Path(__file__).resolve().parent
REPO_ROOT = SERVER_DIR.parent
TENANTS_DIR = SERVER_DIR / "tenants"
DATA_DIR = SERVER_DIR / "data"
KB_INDEX_DIR = SERVER_DIR / "kb_index"
CACHE_DIR = SERVER_DIR / "cache"

# A value that is exactly ``ENV:SOME_VAR`` is replaced by os.environ["SOME_VAR"].
_ENV_REF_RE = re.compile(r"^ENV:([A-Z0-9_]+)$")


def _env_ref(value: Any) -> str | None:
    """Return the env var name if ``value`` is an ``ENV:VAR`` reference."""
    if isinstance(value, str):
        match = _ENV_REF_RE.match(value)
        if match:
            return match.group(1)
    return None


def collect_env_refs(obj: Any) -> set[str]:
    """Recursively collect every ``ENV:VAR`` reference name under ``obj``."""
    refs: set[str] = set()
    if isinstance(obj, Mapping):
        for v in obj.values():
            refs |= collect_env_refs(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            refs |= collect_env_refs(v)
    else:
        name = _env_ref(obj)
        if name:
            refs.add(name)
    return refs


def resolve_env_refs(obj: Any, env: Mapping[str, str]) -> Any:
    """Return a copy of ``obj`` with every ``ENV:VAR`` reference resolved.

    Unset references resolve to ``None`` so callers can detect what is missing
    rather than silently shipping the literal ``"ENV:..."`` string downstream.
    """
    if isinstance(obj, Mapping):
        return {k: resolve_env_refs(v, env) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [resolve_env_refs(v, env) for v in obj]
    name = _env_ref(obj)
    if name:
        return env.get(name) or None
    return obj


@dataclass(frozen=True)
class TenantConfig:
    """A resolved tenant: persona, languages, provider models, and KB settings."""

    id: str
    raw: dict[str, Any]
    missing_keys: list[str] = field(default_factory=list)
    path: Path | None = None

    @property
    def name(self) -> str:
        return self.raw.get("name", self.id)

    @property
    def persona(self) -> dict[str, Any]:
        return self.raw.get("persona", {})

    @property
    def languages(self) -> list[str]:
        return self.raw.get("languages", ["en"])

    @property
    def default_language(self) -> str:
        return self.raw.get("default_language", self.languages[0])

    @property
    def providers(self) -> dict[str, Any]:
        return self.raw.get("providers", {})

    @property
    def kb(self) -> dict[str, Any]:
        return self.raw.get("kb", {})

    @property
    def brand_safety(self) -> dict[str, Any]:
        return self.raw.get("brand_safety", {})

    @property
    def data_dir(self) -> Path:
        return DATA_DIR / self.id

    @property
    def index_path(self) -> Path:
        return index_path(self.id)

    def provider(self, kind: str) -> dict[str, Any]:
        """Provider sub-config for ``stt``/``llm``/``tts``/``avatar``."""
        return self.providers.get(kind, {})


def tenant_path(tenant_id: str) -> Path:
    return TENANTS_DIR / f"{tenant_id}.json"


def index_path(tenant_id: str) -> Path:
    return KB_INDEX_DIR / f"{tenant_id}.json"


def cache_path(tenant_id: str) -> Path:
    return CACHE_DIR / f"{tenant_id}.json"


def load_tenant(tenant_id: str, env: Mapping[str, str] | None = None) -> TenantConfig:
    """Load and resolve a tenant config by id.

    ``missing_keys`` reports the provider credentials (under ``providers``) that
    are referenced but unset — the operator-facing checklist for going live.
    """
    env = os.environ if env is None else env
    path = tenant_path(tenant_id)
    if not path.exists():
        raise FileNotFoundError(
            f"No tenant config at {path}. Available: "
            f"{', '.join(available_tenants()) or '(none)'}"
        )
    raw_unresolved = json.loads(path.read_text(encoding="utf-8"))

    # Missing keys are scoped to the live-voice providers; the KB build path can
    # run fully offline (EMBEDDER=stub), so an unset embedder key isn't "missing".
    provider_refs = collect_env_refs(raw_unresolved.get("providers", {}))
    missing = sorted(ref for ref in provider_refs if not env.get(ref))

    resolved = resolve_env_refs(raw_unresolved, env)
    resolved.setdefault("id", tenant_id)
    return TenantConfig(id=tenant_id, raw=resolved, missing_keys=missing, path=path)


def available_tenants() -> list[str]:
    if not TENANTS_DIR.exists():
        return []
    return sorted(p.stem for p in TENANTS_DIR.glob("*.json"))


def embedder_name(tenant: TenantConfig, env: Mapping[str, str] | None = None) -> str:
    """Resolve which embedder to use: ``EMBEDDER`` env var wins, else tenant KB
    config, else ``stub`` so the engine always has an offline-capable default."""
    env = os.environ if env is None else env
    return env.get("EMBEDDER") or tenant.kb.get("embedder", "stub")

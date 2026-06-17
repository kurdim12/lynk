"""First-class fallback paths.

Every provider can declare a ``fallback`` in the tenant config (same shape).
``resolve_chain`` returns the primary then the fallback, each marked ready/not
based on whether its credentials are actually set, and ``first_ready`` picks the
one to use. The bot uses this to keep talking when the primary provider's keys
are missing or it drops — and to run **audio-only** when the avatar isn't
available (avatar is optional; STT + LLM + TTS are required for a voice answer).

Pure and offline-testable: it reasons about resolved config, not live calls.
"""

from __future__ import annotations

from dataclasses import dataclass

# Credentials that must be present for a provider of each kind to be usable.
REQUIRED_FIELDS = {
    "stt": ("api_key",),
    "llm": ("api_key",),
    "tts": ("api_key", "voice_id"),
    "avatar": ("api_key", "face_id"),
}


@dataclass(frozen=True)
class ProviderOption:
    kind: str
    config: dict
    ready: bool
    is_fallback: bool

    @property
    def provider(self) -> str | None:
        return self.config.get("provider")

    @property
    def model(self) -> str | None:
        return self.config.get("model")


def provider_ready(kind: str, config: dict | None) -> bool:
    """A provider is ready when all of its required credential fields are set."""
    if not config:
        return False
    return all(config.get(field) for field in REQUIRED_FIELDS.get(kind, ("api_key",)))


def resolve_chain(tenant, kind: str) -> list[ProviderOption]:
    """The ordered provider options for a kind: primary, then optional fallback."""
    primary = tenant.provider(kind)
    options: list[ProviderOption] = []
    if primary:
        options.append(ProviderOption(kind, primary, provider_ready(kind, primary), False))
        fallback = primary.get("fallback")
        if fallback:
            options.append(ProviderOption(kind, fallback, provider_ready(kind, fallback), True))
    return options


def first_ready(tenant, kind: str) -> ProviderOption | None:
    """The first ready option for a kind, or None if none are ready."""
    return next((opt for opt in resolve_chain(tenant, kind) if opt.ready), None)


def can_run_audio_only(tenant) -> bool:
    """A voice answer is possible (STT + LLM + TTS ready); avatar is optional."""
    return all(first_ready(tenant, kind) for kind in ("stt", "llm", "tts"))


def use_avatar(tenant) -> bool:
    """Build the avatar into the pipeline only when it's ready; else audio-only."""
    return first_ready(tenant, "avatar") is not None


def audio_only_on_drop(tenant) -> bool:
    """Live resilience: keep talking audio-only if the avatar drops mid-session."""
    return bool(tenant.raw.get("fallbacks", {}).get("audio_only_on_avatar_drop", True))


def readiness_report(tenant) -> dict:
    """Per-kind readiness for the status endpoint."""
    report: dict[str, dict] = {}
    for kind in ("stt", "llm", "tts", "avatar"):
        chain = resolve_chain(tenant, kind)
        report[kind] = {
            "ready": any(opt.ready for opt in chain),
            "options": [
                {
                    "provider": opt.provider,
                    "model": opt.model,
                    "ready": opt.ready,
                    "fallback": opt.is_fallback,
                }
                for opt in chain
            ],
        }
    return report

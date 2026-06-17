from types import SimpleNamespace

from server.config import load_tenant
from server.fallbacks import (
    can_run_audio_only,
    first_ready,
    provider_ready,
    readiness_report,
    resolve_chain,
    use_avatar,
)

ALL_KEYS = {
    "DEEPGRAM_API_KEY": "d",
    "ANTHROPIC_API_KEY": "a",
    "ELEVENLABS_API_KEY": "e",
    "ELEVENLABS_VOICE_ID": "v",
    "SIMLI_API_KEY": "s",
    "SIMLI_FACE_ID": "f",
}


class FakeTenant:
    def __init__(self, providers, raw=None):
        self._providers = providers
        self.raw = raw or {}

    def provider(self, kind):
        return self._providers.get(kind, {})


def test_provider_ready_checks_required_fields():
    assert provider_ready("llm", {"api_key": "x"})
    assert not provider_ready("llm", {"api_key": None})
    assert not provider_ready("tts", {"api_key": "x"})  # missing voice_id
    assert provider_ready("tts", {"api_key": "x", "voice_id": "v"})
    assert not provider_ready("avatar", {"api_key": "x"})  # missing face_id


def test_falls_back_to_secondary_when_primary_unset():
    t = FakeTenant(
        {"llm": {"provider": "anthropic", "api_key": None,
                 "fallback": {"provider": "anthropic", "api_key": "y"}}}
    )
    chain = resolve_chain(t, "llm")
    assert [o.ready for o in chain] == [False, True]
    chosen = first_ready(t, "llm")
    assert chosen.ready and chosen.is_fallback


def test_audio_only_when_avatar_unavailable():
    ready_voice = {
        "stt": {"api_key": "x"},
        "llm": {"api_key": "x"},
        "tts": {"api_key": "x", "voice_id": "v"},
        "avatar": {"api_key": "x"},  # missing face_id → not ready
    }
    t = FakeTenant(ready_voice)
    assert can_run_audio_only(t)
    assert not use_avatar(t)


def test_real_tenant_has_llm_fallback_chain():
    with_keys = load_tenant("lynk-and-co", env=ALL_KEYS)
    chain = resolve_chain(with_keys, "llm")
    assert [o.model for o in chain] == ["claude-opus-4-8", "claude-sonnet-4-6"]
    assert all(o.ready for o in chain)
    assert use_avatar(with_keys)
    assert can_run_audio_only(with_keys)


def test_real_tenant_without_keys_is_not_ready():
    no_keys = load_tenant("lynk-and-co", env={})
    assert not can_run_audio_only(no_keys)
    assert not use_avatar(no_keys)
    report = readiness_report(no_keys)
    assert report["llm"]["ready"] is False
    assert len(report["llm"]["options"]) == 2  # primary + fallback both listed

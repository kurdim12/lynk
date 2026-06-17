import pytest

from server.config import (
    collect_env_refs,
    load_tenant,
    resolve_env_refs,
)


def test_collect_env_refs_finds_nested():
    obj = {"a": "ENV:FOO", "b": ["x", "ENV:BAR"], "c": {"d": "ENV:FOO"}, "e": 3}
    assert collect_env_refs(obj) == {"FOO", "BAR"}


def test_resolve_env_refs_resolves_and_nulls_missing():
    obj = {"k": "ENV:SET", "m": "ENV:UNSET", "lit": "plain"}
    out = resolve_env_refs(obj, env={"SET": "value"})
    assert out == {"k": "value", "m": None, "lit": "plain"}


def test_load_tenant_resolves_keys_and_reports_missing():
    tenant = load_tenant("lynk-and-co", env={"ANTHROPIC_API_KEY": "sk-test"})
    assert tenant.provider("llm")["api_key"] == "sk-test"
    # The other provider keys are unset → reported as missing.
    assert "DEEPGRAM_API_KEY" in tenant.missing_keys
    assert "ANTHROPIC_API_KEY" not in tenant.missing_keys


def test_load_tenant_all_keys_present_means_none_missing():
    env = {
        "DEEPGRAM_API_KEY": "d",
        "ANTHROPIC_API_KEY": "a",
        "ELEVENLABS_API_KEY": "e",
        "ELEVENLABS_VOICE_ID": "v",
        "SIMLI_API_KEY": "s",
        "SIMLI_FACE_ID": "f",
    }
    tenant = load_tenant("lynk-and-co", env=env)
    assert tenant.missing_keys == []


def test_tenant_properties():
    tenant = load_tenant("lynk-and-co", env={})
    assert tenant.name == "Lynk & Co"
    assert tenant.languages == ["ar", "en"]
    assert tenant.default_language == "en"
    assert tenant.persona["name"] == "Noor"
    assert tenant.kb["top_k"] == 4


def test_load_unknown_tenant_raises():
    with pytest.raises(FileNotFoundError):
        load_tenant("no-such-brand", env={})

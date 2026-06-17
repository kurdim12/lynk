import json

import pytest

from scripts.onboard_tenant import scaffold_tenant, tenant_template


def test_template_has_required_shape():
    t = tenant_template("acme-motors", "Acme Motors", ["ar", "en"])
    assert t["id"] == "acme-motors"
    assert t["name"] == "Acme Motors"
    assert t["languages"] == ["ar", "en"]
    assert t["default_language"] == "ar"
    # Per-tenant voice/face env refs, shared provider API keys.
    assert t["providers"]["tts"]["voice_id"] == "ENV:ELEVENLABS_VOICE_ID_ACME_MOTORS"
    assert t["providers"]["avatar"]["face_id"] == "ENV:SIMLI_FACE_ID_ACME_MOTORS"
    assert t["providers"]["llm"]["api_key"] == "ENV:ANTHROPIC_API_KEY"


def test_scaffold_writes_config_and_doc(tmp_path):
    tenants_dir = tmp_path / "tenants"
    data_dir = tmp_path / "data"
    json_path, doc_path = scaffold_tenant(
        "acme-motors", "Acme Motors", ["en"], tenants_dir=tenants_dir, data_dir=data_dir
    )
    assert json_path.exists() and doc_path.exists()
    config = json.loads(json_path.read_text(encoding="utf-8"))
    assert config["name"] == "Acme Motors"
    assert "PLACEHOLDER" in doc_path.read_text(encoding="utf-8")


def test_scaffold_refuses_overwrite_without_force(tmp_path):
    args = ("acme", "Acme", ["en"])
    kwargs = {"tenants_dir": tmp_path / "t", "data_dir": tmp_path / "d"}
    scaffold_tenant(*args, **kwargs)
    with pytest.raises(FileExistsError):
        scaffold_tenant(*args, **kwargs)
    # force overwrites cleanly
    scaffold_tenant(*args, **kwargs, force=True)


def test_scaffold_rejects_bad_id(tmp_path):
    with pytest.raises(ValueError):
        scaffold_tenant("Acme Motors", "Acme", ["en"], tenants_dir=tmp_path, data_dir=tmp_path)

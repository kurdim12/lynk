from server.brain.system_prompt import build_system_prompt, detect_language


def test_detect_language():
    assert detect_language("ما هي مدة الضمان؟") == "ar"
    assert detect_language("What is the range?") == "en"
    assert detect_language("", default="en") == "en"


def test_prompt_with_context_includes_grounding_and_rules(tenant):
    prompt = build_system_prompt(
        tenant, grounding="GROUNDED-CONTEXT-BLOCK", language="en", has_context=True
    )
    assert "Noor" in prompt
    assert "Lynk & Co" in prompt
    assert "Answer ONLY" in prompt
    assert "APPROVED KNOWLEDGE" in prompt
    assert "GROUNDED-CONTEXT-BLOCK" in prompt
    assert "English" in prompt
    # Allowed topics from the tenant config are surfaced.
    assert "test drives" in prompt.lower()


def test_prompt_without_context_triggers_safe_refusal(tenant):
    prompt = build_system_prompt(tenant, grounding="", language="en", has_context=False)
    assert "No approved knowledge matched" in prompt
    assert tenant.brand_safety["refusal_en"] in prompt


def test_arabic_prompt_uses_arabic_language_and_refusal(tenant):
    prompt = build_system_prompt(tenant, grounding="", language="ar", has_context=False)
    assert "Arabic" in prompt
    assert tenant.brand_safety["refusal_ar"] in prompt

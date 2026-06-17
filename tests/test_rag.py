from server.brain.rag import RAGGrounder, last_user_text, with_system_prompt


def test_ground_english_question(tenant, retriever):
    g = RAGGrounder(tenant, retriever).ground("What is the electric driving range?")
    assert g.language == "en"
    assert g.has_context
    assert g.chunks
    assert "APPROVED KNOWLEDGE" in g.system_prompt
    assert "Powertrain" in g.context_text


def test_ground_arabic_question(tenant, retriever):
    g = RAGGrounder(tenant, retriever).ground("ما هي مدة الضمان؟")
    assert g.language == "ar"
    assert g.has_context
    assert "Arabic" in g.system_prompt


def test_ground_off_topic_is_safe(tenant, retriever):
    g = RAGGrounder(tenant, retriever).ground("What is the weather today in Tokyo?")
    assert not g.has_context
    assert g.chunks == []
    assert "No approved knowledge matched" in g.system_prompt


def test_explicit_language_overrides_detection(tenant, retriever):
    g = RAGGrounder(tenant, retriever).ground("range?", language="ar")
    assert g.language == "ar"


def test_last_user_text_handles_str_and_parts():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "reply"},
        {"role": "user", "content": [{"type": "text", "text": "latest question"}]},
    ]
    assert last_user_text(messages) == "latest question"


def test_with_system_prompt_keeps_single_system_and_preserves_turns():
    messages = [
        {"role": "system", "content": "old"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    out = with_system_prompt(messages, "GROUNDED")
    assert out[0] == {"role": "system", "content": "GROUNDED"}
    assert sum(1 for m in out if m["role"] == "system") == 1
    assert out[1:] == messages[1:]

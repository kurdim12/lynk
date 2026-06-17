import pytest

from server.config import load_tenant
from server.kb.retriever import Retriever


def test_english_query_retrieves_the_right_section(retriever):
    results = retriever.retrieve("What is the electric driving range?")
    assert results, "expected at least one grounded passage"
    assert results[0].chunk.section.startswith("Powertrain")


def test_arabic_query_retrieves_arabic_section(retriever):
    results = retriever.retrieve("ما هي مدة الضمان؟")
    sections = [r.chunk.section for r in results]
    assert any("الضمان" in s for s in sections)


def test_off_topic_query_returns_nothing_above_floor(retriever):
    # Below min_score → no grounding → triggers the safe-refusal path.
    assert retriever.retrieve("What is the weather today in Tokyo?") == []


def test_results_sorted_by_score(retriever):
    results = retriever.retrieve("charging the battery at home")
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_embedder_mismatch_is_rejected(built_index):
    # Index was built with the stub embedder; asking for voyage must error
    # (different vector spaces) rather than silently return garbage.
    tenant = load_tenant("lynk-and-co", env={})
    with pytest.raises(ValueError, match="mismatch"):
        Retriever.from_tenant(tenant, env={"EMBEDDER": "voyage"})


def test_missing_index_raises(tmp_path, monkeypatch):
    import server.config as config

    monkeypatch.setattr(config, "KB_INDEX_DIR", tmp_path)
    fresh = load_tenant("lynk-and-co", env={})
    with pytest.raises(FileNotFoundError):
        Retriever.from_tenant(fresh, env={"EMBEDDER": "stub"})

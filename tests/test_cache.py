from server.cache import AnswerCache, normalize_question

from scripts.prerender_cache import prerender
from server.brain.rag import RAGGrounder


def test_normalize_is_case_space_and_punctuation_insensitive():
    base = normalize_question("What is the range?")
    assert normalize_question("  what is the   RANGE  ") == base
    assert normalize_question("What is the range") == base
    assert normalize_question("ما هي مدة الضمان؟") == normalize_question("ما هي مدة الضمان")


def test_put_get_hit_and_miss():
    cache = AnswerCache()
    cache.put("What is the range?", "en", "About 69 km.")
    hit = cache.get("  what is the RANGE ", "en")  # normalized variant still hits
    assert hit is not None and hit.answer == "About 69 km."
    assert cache.get("What is the range?", "ar") is None  # language-separated
    assert cache.get("unknown question", "en") is None


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "cache.json"
    cache = AnswerCache(path)
    cache.put("How long is the warranty?", "en", "5 years.", sections=["Warranty"])
    cache.save()

    loaded = AnswerCache.load(path)
    assert len(loaded) == 1
    entry = loaded.get("how long is the warranty", "en")
    assert entry.answer == "5 years."
    assert entry.sections == ["Warranty"]


def test_for_tenant_empty_when_not_rendered():
    assert len(AnswerCache.for_tenant("no-such-tenant-xyz")) == 0


def test_prerender_fills_cache(tenant, retriever):
    grounder = RAGGrounder(tenant, retriever)
    cache = AnswerCache()
    questions = ["What is the electric driving range?", "ما هي مدة الضمان؟"]
    count = prerender(grounder, questions, lambda g: f"ANSWER[{g.language}]", cache)

    assert count == 2 and len(cache) == 2
    en = cache.get("What is the electric driving range?", "en")
    assert en.answer == "ANSWER[en]"
    assert en.sections  # grounded sections recorded
    assert cache.get("ما هي مدة الضمان؟", "ar").answer == "ANSWER[ar]"

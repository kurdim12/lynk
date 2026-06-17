import math

import pytest

from server.kb.embedder import StubEmbedder, get_embedder


def test_stub_is_deterministic():
    e = StubEmbedder()
    assert e.embed_query("electric range") == e.embed_query("electric range")


def test_stub_vectors_are_unit_length():
    e = StubEmbedder()
    v = e.embed_query("warranty and ownership")
    assert abs(math.sqrt(sum(x * x for x in v)) - 1.0) < 1e-9
    assert len(v) == e.dim


def test_related_text_scores_higher_than_unrelated():
    e = StubEmbedder()

    def cos(a, b):
        return sum(x * y for x, y in zip(a, b))  # both unit vectors

    q = e.embed_query("electric driving range")
    related = e.embed_documents(["The electric range is about 69 km on a charge."])[0]
    unrelated = e.embed_documents(["Book a showroom visit with a valid licence."])[0]
    assert cos(q, related) > cos(q, unrelated)


def test_empty_text_is_zero_vector():
    e = StubEmbedder()
    assert e.embed_query("") == [0.0] * e.dim


def test_factory_returns_stub_and_rejects_unknown():
    assert get_embedder("stub").name == "stub"
    with pytest.raises(ValueError):
        get_embedder("bogus")

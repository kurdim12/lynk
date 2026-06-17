from server.kb.types import Chunk
from server.kb.vector_store import InMemoryVectorStore


def _chunk(cid: str) -> Chunk:
    return Chunk(id=cid, text=f"text {cid}", source="s.md", section=cid)


def test_search_orders_by_cosine_and_respects_top_k():
    store = InMemoryVectorStore(embedder="stub", dim=3)
    store.add(
        [_chunk("a"), _chunk("b"), _chunk("c")],
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.9, 0.1, 0.0]],
    )
    results = store.search([1.0, 0.0, 0.0], top_k=2)
    assert [r.chunk.id for r in results] == ["a", "c"]
    assert results[0].score > results[1].score
    assert len(results) == 2


def test_len_tracks_added_chunks():
    store = InMemoryVectorStore()
    assert len(store) == 0
    store.add([_chunk("a")], [[1.0, 0.0]])
    assert len(store) == 1


def test_save_and_load_round_trip(tmp_path):
    store = InMemoryVectorStore(embedder="stub", dim=2)
    store.add([_chunk("a"), _chunk("b")], [[1.0, 0.0], [0.0, 1.0]])
    path = tmp_path / "idx.json"
    store.save(path)

    loaded = InMemoryVectorStore.load(path)
    assert loaded.embedder == "stub"
    assert loaded.dim == 2
    assert len(loaded) == 2
    results = loaded.search([1.0, 0.0], top_k=1)
    assert results[0].chunk.id == "a"
    assert results[0].chunk.section == "a"

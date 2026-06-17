import json


def test_ingest_builds_index(built_index):
    result = built_index
    assert result.tenant_id == "lynk-and-co"
    assert result.embedder == "stub"
    assert result.chunks > 0
    assert "vehicle-info.md" in result.documents
    assert result.index_path.exists()


def test_index_file_is_valid_and_matches_chunk_count(built_index):
    data = json.loads(built_index.index_path.read_text(encoding="utf-8"))
    assert data["embedder"] == "stub"
    assert data["dim"] > 0
    assert len(data["items"]) == built_index.chunks
    # Every persisted item carries its chunk + a same-dimension vector.
    item = data["items"][0]
    assert set(item) == {"chunk", "vector"}
    assert len(item["vector"]) == data["dim"]

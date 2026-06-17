from server.kb.chunker import chunk_markdown

DOC = """# Title

Intro paragraph under the title.

## Section One

First section body paragraph.

## Section Two

Second section body paragraph.
"""


def test_chunks_are_section_scoped_and_heading_tagged():
    chunks = chunk_markdown(DOC, "doc.md", chunk_size=700, chunk_overlap=120)
    sections = [c.section for c in chunks]
    assert sections == ["Title", "Section One", "Section Two"]
    # Heading text is embedded with the body so topic keywords aid retrieval.
    for c in chunks:
        assert c.text.startswith(c.section)
    # Ids are stable and ordered.
    assert [c.ordinal for c in chunks] == [0, 1, 2]
    assert chunks[0].id == "doc-0000"
    assert chunks[0].source == "doc.md"


def test_long_section_splits_with_overlap():
    paras = "\n\n".join(f"PARA{i} " + "word " * 12 for i in range(6))
    text = f"# Big\n\n{paras}"
    chunks = chunk_markdown(text, "big.md", chunk_size=160, chunk_overlap=90)
    assert len(chunks) > 1
    # Every paragraph survives somewhere.
    joined = " ".join(c.text for c in chunks)
    for i in range(6):
        assert f"PARA{i}" in joined
    # Overlap: at least one paragraph appears in two different chunks.
    shared = [
        i
        for i in range(6)
        if sum(f"PARA{i}" in c.text for c in chunks) > 1
    ]
    assert shared, "expected block-level overlap between consecutive chunks"


def test_content_before_first_heading_has_empty_section():
    chunks = chunk_markdown("Just a lead paragraph.", "x.md")
    assert len(chunks) == 1
    assert chunks[0].section == ""
    assert chunks[0].text == "Just a lead paragraph."

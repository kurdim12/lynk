"""Markdown-aware chunker.

Splits approved docs into coherent, retrievable passages. It is heading-aware:
each markdown section becomes its own chunk (long sections are split, with
block-level overlap so context isn't cut mid-sentence), and the heading text is
embedded with the body so topic keywords ("Warranty", "الضمان") strengthen
retrieval. Each chunk records the section it came from for citation.
"""

from __future__ import annotations

import re
from pathlib import Path

from server.kb.types import Chunk

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?؟。])\s+")

DEFAULT_CHUNK_SIZE = 700
DEFAULT_CHUNK_OVERLAP = 120


def _split_long_block(block: str, size: int) -> list[str]:
    """Split an over-long block into <=size pieces on sentence then word bounds."""
    if len(block) <= size:
        return [block]
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_SPLIT_RE.split(block):
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > size:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)

    out: list[str] = []
    for piece in pieces:
        if len(piece) <= size:
            out.append(piece)
            continue
        buf = ""
        for word in piece.split():
            candidate = f"{buf} {word}".strip()
            if buf and len(candidate) > size:
                out.append(buf)
                buf = word
            else:
                buf = candidate
        if buf:
            out.append(buf)
    return out


def _blocks_with_sections(text: str) -> list[tuple[str, str]]:
    """Parse markdown into ``(section, block)`` pairs, tracking the current heading."""
    section = ""
    result: list[tuple[str, str]] = []
    for raw in re.split(r"\n\s*\n", text):
        lines = raw.strip().splitlines()
        body: list[str] = []
        for line in lines:
            heading = _HEADING_RE.match(line.strip())
            if heading:
                if body:
                    result.append((section, "\n".join(body).strip()))
                    body = []
                section = heading.group(2).strip()
            else:
                body.append(line)
        if body:
            result.append((section, "\n".join(body).strip()))
    return [(s, b) for s, b in result if b]


def _pack_blocks(blocks: list[str], size: int, overlap: int) -> list[str]:
    """Greedily pack blocks up to ``size`` chars, with block-level overlap."""
    pieces: list[str] = []
    buf: list[str] = []
    buf_len = 0

    def flush(reseed: bool) -> None:
        nonlocal buf, buf_len
        if not buf:
            return
        pieces.append("\n\n".join(buf).strip())
        if not reseed:
            buf, buf_len = [], 0
            return
        carry: list[str] = []
        carry_len = 0
        for blk in reversed(buf):
            blk_len = len(blk) + 2
            if carry_len + blk_len > overlap and carry:
                break
            carry.insert(0, blk)
            carry_len += blk_len
        if len(carry) == len(buf):  # never let overlap be the whole piece
            carry = carry[1:]
        buf = list(carry)
        buf_len = sum(len(b) + 2 for b in buf)

    for block in blocks:
        blk_len = len(block) + 2
        if buf and buf_len + blk_len > size:
            flush(reseed=True)
        buf.append(block)
        buf_len += blk_len
    flush(reseed=False)
    return pieces


def chunk_markdown(
    text: str,
    source: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """Chunk a markdown document into section-scoped, heading-tagged ``Chunk``s."""
    stem = Path(source).stem or "doc"
    pairs = _blocks_with_sections(text)

    # Group consecutive blocks by their section, preserving document order.
    sections: list[tuple[str, list[str]]] = []
    for section, block in pairs:
        if sections and sections[-1][0] == section:
            sections[-1][1].append(block)
        else:
            sections.append((section, [block]))

    chunks: list[Chunk] = []
    for section, blocks in sections:
        # Split any over-long block first, then pack to size within the section.
        expanded: list[str] = []
        for block in blocks:
            expanded.extend(_split_long_block(block, chunk_size))
        for piece in _pack_blocks(expanded, chunk_size, chunk_overlap):
            ordinal = len(chunks)
            body = f"{section}\n\n{piece}" if section else piece
            chunks.append(
                Chunk(
                    id=f"{stem}-{ordinal:04d}",
                    text=body,
                    source=source,
                    section=section,
                    ordinal=ordinal,
                )
            )
    return chunks

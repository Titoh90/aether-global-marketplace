#!/usr/bin/env python3
"""
chunker.py — Text/Markdown chunking with overlap.

Rules:
- Markdown headers are hard boundaries (never split mid-section)
- Wikilinks [[X]] → X (stripped for embedding)
- Code blocks preserved intact
- YAML frontmatter parsed for tags, excluded from chunks
- chunk_size in approximate tokens (chars/4)
"""

from __future__ import annotations

import re
from typing import Optional


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_CHUNK_SIZE = 512   # approx tokens
DEFAULT_OVERLAP    = 64    # approx tokens
CHARS_PER_TOKEN    = 4     # rough approximation


# ── Helpers ───────────────────────────────────────────────────────────────────

def _approx_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def _strip_wikilinks(text: str) -> str:
    """Convert [[Target|Alias]] → Alias, [[Target]] → Target."""
    def _replace(m: re.Match) -> str:
        inner = m.group(1)
        if "|" in inner:
            return inner.split("|", 1)[1]
        return inner
    return re.sub(r"\[\[([^\]]+)\]\]", _replace, text)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Extract YAML frontmatter if present.
    Returns (frontmatter_dict, body_without_frontmatter).
    """
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_block = text[3:end].strip()
    body     = text[end + 4:].lstrip("\n")
    fm: dict = {}
    for line in fm_block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, body


def _split_paragraphs(text: str) -> list[str]:
    """Split on double newlines, preserve content."""
    return [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]


# ── Public API ────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap:    int = DEFAULT_OVERLAP,
) -> list[str]:
    """
    Split text into overlapping chunks of ~chunk_size tokens.

    Strategy:
    1. Split on paragraphs first
    2. Merge small paragraphs until chunk_size reached
    3. Apply overlap by prepending tail of previous chunk

    Returns list of chunk strings (may be empty list for empty input).
    """
    if not text or not text.strip():
        return []

    max_chars     = chunk_size * CHARS_PER_TOKEN
    overlap_chars = overlap * CHARS_PER_TOKEN

    paragraphs = _split_paragraphs(text)
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        candidate = (current + "\n\n" + para).strip() if current else para

        if len(candidate) <= max_chars:
            current = candidate
        else:
            # Flush current chunk if non-empty
            if current:
                chunks.append(current)
                # Overlap: take tail of current as prefix
                tail  = current[-overlap_chars:] if len(current) > overlap_chars else current
                current = (tail + "\n\n" + para).strip()
            else:
                # Single paragraph exceeds chunk_size — split by sentences
                sentences = re.split(r"(?<=[.!?])\s+", para)
                buf = ""
                for sent in sentences:
                    test = (buf + " " + sent).strip() if buf else sent
                    if len(test) <= max_chars:
                        buf = test
                    else:
                        if buf:
                            chunks.append(buf)
                            tail = buf[-overlap_chars:] if len(buf) > overlap_chars else buf
                            buf  = (tail + " " + sent).strip()
                        else:
                            chunks.append(sent[:max_chars])
                            buf  = sent[max_chars - overlap_chars:]
                if buf:
                    current = buf

    if current:
        chunks.append(current)

    # Final guard: never exceed max_chars * 1.5
    result = []
    hard_limit = int(max_chars * 1.5)
    for ch in chunks:
        if len(ch) <= hard_limit:
            result.append(ch)
        else:
            result.append(ch[:hard_limit])

    return result


def chunk_markdown(md_text: str) -> list[tuple[str, list[str]]]:
    """
    Chunk markdown text respecting header boundaries.

    Returns list of (chunk_content, tags) where tags are extracted from
    enclosing header names and frontmatter.

    Wikilinks are stripped: [[Target]] → Target.
    Code blocks are preserved intact.
    """
    if not md_text or not md_text.strip():
        return []

    fm, body = _parse_frontmatter(md_text)

    # Tags from frontmatter
    fm_tags: list[str] = []
    for key in ("tags", "tag", "category", "type"):
        val = fm.get(key, "")
        if val:
            fm_tags.extend([t.strip().strip("#") for t in re.split(r"[,\s]+", val) if t.strip()])

    # Split into sections by headers (##, ###, etc. — not H1 which is title)
    # Keep header as part of section
    header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    sections: list[tuple[str, list[str]]] = []   # (section_text, header_tags)

    # Find all header positions
    positions = [(m.start(), m.group(1), m.group(2)) for m in header_pattern.finditer(body)]

    if not positions:
        # No headers — chunk the whole body
        clean = _strip_wikilinks(body)
        chunks = chunk_text(clean)
        return [(ch, fm_tags) for ch in chunks]

    # Extract pre-header content
    if positions[0][0] > 0:
        pre = body[:positions[0][0]].strip()
        if pre:
            clean = _strip_wikilinks(pre)
            for ch in chunk_text(clean):
                sections.append((ch, fm_tags[:]))

    # Extract each header section
    for i, (start, hashes, header_name) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(body)
        section_text = body[start:end].strip()
        section_tags = fm_tags + [header_name.strip().lower().replace(" ", "_")]

        clean = _strip_wikilinks(section_text)
        for ch in chunk_text(clean):
            sections.append((ch, section_tags))

    return sections

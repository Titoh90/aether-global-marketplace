#!/usr/bin/env python3
"""
schemas.py — Frozen dataclasses for core/knowledge_core.

All schemas are frozen=True — no runtime mutation.
"""

from __future__ import annotations

from dataclasses import dataclass


# ── Memory types ──────────────────────────────────────────────────────────────

MEMORY_TYPES: frozenset[str] = frozenset({
    "technical",
    "prompt",
    "revenue",
    "visual_archetype",
    "failure",
    "provider_reliability",
    "architecture",
    "tooling",
})

EMBEDDING_DIM: int = 384



# ── Schemas ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class KnowledgeChunk:
    """
    A single unit of knowledge extracted from a source document.

    chunk_id:    SHA256[:16] of content — deterministic, dedup key
    content:     raw text of this chunk
    source_file: relative path (from vault root or IMPERIO_ROOT)
    memory_type: one of MEMORY_TYPES
    tags:        extracted from markdown headers or explicit tagging
    created_at:  ISO timestamp
    chunk_index: position within source file (0-based)
    embedding_dim: 384 for all-MiniLM-L6-v2
    """
    chunk_id:      str
    content:       str
    source_file:   str
    memory_type:   str
    tags:          tuple
    created_at:    str
    chunk_index:   int
    embedding_dim: int = 384


@dataclass(frozen=True)
class SearchResult:
    """Result from search_memory()."""
    chunk: KnowledgeChunk
    score: float   # cosine similarity [0, 1]
    rank:  int     # 1-based rank in result set

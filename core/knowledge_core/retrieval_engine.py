#!/usr/bin/env python3
"""
retrieval_engine.py — LOCAL memory retrieval PUBLIC API.

100% LOCAL — zero network calls, zero provider calls.
Used by dispatch.py for memory_retrieval (local-only gate).
Used by Claude Code for context injection.

Usage:
    from core.knowledge_core.retrieval_engine import search_memory, format_for_context

    results = search_memory("IMPERIO pipeline architecture", top_k=5)
    context = format_for_context(results, max_tokens=2000)
"""

from __future__ import annotations

import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.knowledge_core.schemas import SearchResult
from core.knowledge_core.embedding_cache import get_embedding
from core.knowledge_core import knowledge_store as ks

CHARS_PER_TOKEN = 4


# ── Public API ────────────────────────────────────────────────────────────────

def search_memory(
    query:       str,
    memory_type: str | None = None,
    top_k:       int = 5,
) -> list[SearchResult]:
    """
    Retrieve relevant knowledge chunks for a query.

    100% LOCAL — no internet, no provider calls.

    Args:
        query:       natural language query
        memory_type: if set, search only that type; if None, search all types
        top_k:       max results to return

    Returns:
        list of SearchResult sorted by score descending
        Empty list if nothing indexed or query empty.
    """
    if not query or not query.strip():
        return []

    try:
        query_emb = get_embedding(query)
    except Exception:
        return []

    try:
        if memory_type is not None:
            raw = ks.search(memory_type, query_emb, top_k=top_k)
            results = [
                SearchResult(chunk=chunk, score=score, rank=i + 1)
                for i, (score, chunk) in enumerate(raw)
            ]
        else:
            results = ks.search_all_types(query_emb, top_k=top_k)
    except Exception:
        return []

    return results


def format_for_context(
    results:    list[SearchResult],
    max_tokens: int = 1000,
) -> str:
    """
    Format search results as a context string for prompt injection.

    Respects token budget (max_tokens). Truncates gracefully.
    Includes source file and score for traceability.

    Returns empty string if results is empty.
    """
    if not results:
        return ""

    max_chars = max_tokens * CHARS_PER_TOKEN
    lines: list[str] = []
    total_chars = 0

    header = "=== KNOWLEDGE CONTEXT ===\n"
    lines.append(header)
    total_chars += len(header)

    for result in results:
        chunk = result.chunk
        entry_header = (
            f"\n[{result.rank}] {chunk.source_file} "
            f"(type={chunk.memory_type}, score={result.score:.3f})\n"
        )
        content_preview = chunk.content

        entry = entry_header + content_preview + "\n"

        if total_chars + len(entry) > max_chars:
            # Try truncated content
            budget    = max_chars - total_chars - len(entry_header) - 10
            if budget > 50:
                truncated = chunk.content[:budget] + "…"
                entry     = entry_header + truncated + "\n"
                lines.append(entry)
            break

        lines.append(entry)
        total_chars += len(entry)

    lines.append("=== END KNOWLEDGE CONTEXT ===")
    return "".join(lines)

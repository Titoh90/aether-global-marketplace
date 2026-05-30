#!/usr/bin/env python3
"""
semantic_memory.py — Auto-persist learnings to knowledge store.

append-only JSONL queue → batch indexed by vault_indexer.

Usage:
    from core.knowledge_core.semantic_memory import persist_learning
    persist_learning("OpenRouter timeout at 30s", "provider_reliability", tags=["openrouter"])

Queue: memory/persist_queue.jsonl — append-only, never mutate existing entries.
Indexing: vault_indexer picks up queue on next batch run.
Non-blocking: writes to queue file only, never computes embeddings inline.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.knowledge_core.schemas import KnowledgeChunk, MEMORY_TYPES

PERSIST_QUEUE = _IMPERIO_ROOT / "memory" / "persist_queue.jsonl"
PERSIST_QUEUE.parent.mkdir(parents=True, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _make_chunk_id(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _append_to_queue(entry: dict) -> None:
    """Append entry to persist_queue.jsonl. Silent on failure."""
    try:
        with open(PERSIST_QUEUE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── Public API ────────────────────────────────────────────────────────────────

def persist_learning(
    content:     str,
    memory_type: str,
    tags:        list[str] | None = None,
    source:      str = "auto",
) -> KnowledgeChunk:
    """
    Persist a learning to the knowledge queue.

    Non-blocking — writes to append-only JSONL queue.
    vault_indexer.index_persist_queue() processes on next batch run.

    Args:
        content:     text to persist
        memory_type: one of MEMORY_TYPES
        tags:        optional tag list
        source:      source identifier (default "auto")

    Returns:
        KnowledgeChunk (not yet indexed — queued for batch)
    """
    if tags is None:
        tags = []

    if memory_type not in MEMORY_TYPES:
        memory_type = "technical"

    chunk_id = _make_chunk_id(content)
    now      = _now_iso()

    chunk = KnowledgeChunk(
        chunk_id    = chunk_id,
        content     = content,
        source_file = source,
        memory_type = memory_type,
        tags        = tuple(tags),
        created_at  = now,
        chunk_index = 0,
    )

    _append_to_queue({
        "chunk_id":    chunk_id,
        "content":     content,
        "source_file": source,
        "memory_type": memory_type,
        "tags":        tags,
        "created_at":  now,
        "chunk_index": 0,
    })

    return chunk


def persist_architecture_decision(
    title:     str,
    decision:  str,
    rationale: str,
) -> None:
    """Persist an architecture decision to 'architecture' memory."""
    content = f"DECISION: {title}\n\n{decision}\n\nRATIONALE: {rationale}"
    persist_learning(
        content     = content,
        memory_type = "architecture",
        tags        = ["decision", title.lower().replace(" ", "_")],
        source      = "architecture_decision",
    )


def persist_provider_event(
    provider:   str,
    event_type: str,
    details:    str,
) -> None:
    """Persist a provider reliability event."""
    content = f"PROVIDER: {provider}\nEVENT: {event_type}\n\n{details}"
    persist_learning(
        content     = content,
        memory_type = "provider_reliability",
        tags        = [provider.lower(), event_type.lower()],
        source      = "provider_event",
    )


def persist_revenue_insight(
    product: str,
    insight: str,
    score:   float,
) -> None:
    """Persist a revenue/affiliate insight."""
    content = f"PRODUCT: {product}\nSCORE: {score:.2f}\n\n{insight}"
    persist_learning(
        content     = content,
        memory_type = "revenue",
        tags        = ["affiliate", product.lower().replace(" ", "_")],
        source      = "revenue_insight",
    )


def persist_prompt_success(
    formula:  str,
    result:   str,
    platform: str,
) -> None:
    """Persist a successful prompt formula."""
    content = f"PLATFORM: {platform}\nFORMULA: {formula}\n\nRESULT: {result}"
    persist_learning(
        content     = content,
        memory_type = "prompt",
        tags        = ["formula", platform.lower()],
        source      = "prompt_success",
    )

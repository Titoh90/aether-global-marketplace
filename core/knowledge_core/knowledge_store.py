#!/usr/bin/env python3
"""
knowledge_store.py — FAISS-backed knowledge store per memory_type.

Pattern from core/visual_intelligence/vector_store.py:
- One FAISS IndexFlatIP (cosine via L2-normalized vectors) per memory_type
- Parallel .meta.json (list of KnowledgeChunk dicts)
- Thread-safe per-namespace locks
- Dedup by chunk_id (SHA256[:16] of content)

Storage:
    memory/vector_store/
        {memory_type}.index      — FAISS IndexFlatIP
        {memory_type}.meta.json  — list of chunk dicts

100% LOCAL — zero AI calls.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Optional

import numpy as np

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.knowledge_core.schemas import KnowledgeChunk, SearchResult, EMBEDDING_DIM

STORE_DIR = _IMPERIO_ROOT / "memory" / "vector_store"
STORE_DIR.mkdir(parents=True, exist_ok=True)

_namespace_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()

EMBEDDING_DIM = 384


# ── Lock management ───────────────────────────────────────────────────────────

def _get_lock(namespace: str) -> threading.Lock:
    with _locks_lock:
        if namespace not in _namespace_locks:
            _namespace_locks[namespace] = threading.Lock()
        return _namespace_locks[namespace]


# ── FAISS index I/O ───────────────────────────────────────────────────────────

def _index_path(namespace: str) -> Path:
    return STORE_DIR / f"{namespace}.index"


def _meta_path(namespace: str) -> Path:
    return STORE_DIR / f"{namespace}.meta.json"


def _load_index(namespace: str):
    """Load or create FAISS IndexFlatIP."""
    import faiss
    path = _index_path(namespace)
    if path.exists():
        try:
            return faiss.read_index(str(path))
        except Exception:
            pass
    return faiss.IndexFlatIP(EMBEDDING_DIM)


def _save_index(namespace: str, index) -> None:
    import faiss
    try:
        faiss.write_index(index, str(_index_path(namespace)))
    except Exception:
        pass


def _load_meta(namespace: str) -> list[dict]:
    path = _meta_path(namespace)
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return []


def _save_meta(namespace: str, meta_list: list[dict]) -> None:
    try:
        _meta_path(namespace).write_text(
            json.dumps(meta_list, ensure_ascii=False, indent=2)
        )
    except Exception:
        pass


def _normalize(vec: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vec)
    if norm > 1e-9:
        return (vec / norm).astype(np.float32)
    return vec.astype(np.float32)


def _chunk_to_dict(chunk: KnowledgeChunk) -> dict:
    return {
        "chunk_id":      chunk.chunk_id,
        "content":       chunk.content,
        "source_file":   chunk.source_file,
        "memory_type":   chunk.memory_type,
        "tags":          list(chunk.tags),
        "created_at":    chunk.created_at,
        "chunk_index":   chunk.chunk_index,
        "embedding_dim": chunk.embedding_dim,
    }


def _dict_to_chunk(d: dict) -> KnowledgeChunk:
    return KnowledgeChunk(
        chunk_id      = d["chunk_id"],
        content       = d["content"],
        source_file   = d.get("source_file", ""),
        memory_type   = d.get("memory_type", "technical"),
        tags          = tuple(d.get("tags", [])),
        created_at    = d.get("created_at", ""),
        chunk_index   = d.get("chunk_index", 0),
        embedding_dim = d.get("embedding_dim", EMBEDDING_DIM),
    )


# ── Public API ────────────────────────────────────────────────────────────────

def add_chunk(
    memory_type: str,
    embedding:   np.ndarray,
    chunk:       KnowledgeChunk,
) -> int:
    """
    Add one chunk to the memory_type FAISS index.

    Dedup by chunk_id — if already exists, returns existing row index.
    Thread-safe per memory_type.
    Returns row index (0-based).
    """
    with _get_lock(memory_type):
        meta_list = _load_meta(memory_type)

        # Dedup by chunk_id
        for i, m in enumerate(meta_list):
            if m.get("chunk_id") == chunk.chunk_id:
                return i

        index = _load_index(memory_type)
        emb   = _normalize(embedding)
        index.add(emb.reshape(1, -1))
        meta_list.append(_chunk_to_dict(chunk))

        _save_index(memory_type, index)
        _save_meta(memory_type, meta_list)

        return len(meta_list) - 1


def search(
    memory_type: str,
    query_emb:   np.ndarray,
    top_k:       int = 5,
) -> list[tuple[float, KnowledgeChunk]]:
    """
    Search one memory_type index.
    Returns list of (score, chunk) sorted by score descending.
    """
    with _get_lock(memory_type):
        meta_list = _load_meta(memory_type)
        if not meta_list:
            return []

        index = _load_index(memory_type)
        if index.ntotal == 0:
            return []

        q   = _normalize(query_emb).reshape(1, -1)
        k   = min(top_k, index.ntotal)
        scores, indices = index.search(q, k)

        results: list[tuple[float, KnowledgeChunk]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(meta_list):
                continue
            chunk = _dict_to_chunk(meta_list[idx])
            results.append((float(score), chunk))

        return sorted(results, key=lambda x: x[0], reverse=True)


def search_all_types(
    query_emb: np.ndarray,
    top_k:     int = 5,
) -> list[SearchResult]:
    """
    Search across all memory_type indices, merge and re-rank.
    Returns list of SearchResult sorted by score descending.
    """
    all_results: list[tuple[float, KnowledgeChunk]] = []

    for namespace in list_types():
        try:
            results = search(namespace, query_emb, top_k=top_k)
            all_results.extend(results)
        except Exception:
            continue

    # Re-rank globally
    all_results.sort(key=lambda x: x[0], reverse=True)
    top = all_results[:top_k]

    return [
        SearchResult(chunk=chunk, score=score, rank=i + 1)
        for i, (score, chunk) in enumerate(top)
    ]


def count(memory_type: str) -> int:
    """Return number of chunks in a memory_type index."""
    with _get_lock(memory_type):
        meta_list = _load_meta(memory_type)
        return len(meta_list)


def list_types() -> list[str]:
    """Return list of memory_types that have been indexed."""
    types: list[str] = []
    try:
        for p in STORE_DIR.glob("*.meta.json"):
            types.append(p.name.split(".")[0])
    except Exception:
        pass
    return sorted(types)


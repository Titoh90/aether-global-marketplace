#!/usr/bin/env python3
"""
vector_store.py — FAISS-backed embedding store with metadata.

Storage layout:
    logs/visual_intelligence/
        vector_store/
            {product_id}.index     — FAISS IndexFlatIP (inner product, L2-normalized = cosine)
            {product_id}.meta.json — list of ImageEmbedding metadata dicts (parallel to index rows)

One index per product_id. Global search across products via iterate-all.

Thread-safe via per-product locks.
ZERO AI calls.
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

from core.visual_intelligence.schemas import ImageEmbedding
from core.visual_intelligence.clip_encoder import EMBEDDING_DIM

_STORE_DIR = _IMPERIO_ROOT / "logs" / "visual_intelligence" / "vector_store"
_STORE_DIR.mkdir(parents=True, exist_ok=True)

_product_locks: dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


# ── Lock management ───────────────────────────────────────────────────────────

def _get_lock(product_id: str) -> threading.Lock:
    with _locks_lock:
        if product_id not in _product_locks:
            _product_locks[product_id] = threading.Lock()
        return _product_locks[product_id]


# ── Public API ────────────────────────────────────────────────────────────────

def add_embedding(
    product_id: str,
    embedding:  np.ndarray,
    metadata:   ImageEmbedding,
) -> int:
    """
    Add one embedding to the product's FAISS index.

    Args:
        product_id: ASIN — determines which index to write to
        embedding:  float32 array shape (EMBEDDING_DIM,) — L2-normalized
        metadata:   ImageEmbedding with post_id, platform, etc.

    Returns:
        Row index in FAISS (0-based)

    Idempotent: if metadata.image_hash already exists → skip (returns existing row)
    """
    with _get_lock(product_id):
        meta_list = _load_meta(product_id)

        # Dedup by image_hash
        for i, m in enumerate(meta_list):
            if m.get("image_hash") == metadata.image_hash:
                return i

        index = _load_index(product_id)
        emb   = _normalize(embedding)
        index.add(emb.reshape(1, -1))

        meta_list.append(metadata.to_dict())
        _save_index(product_id, index)
        _save_meta(product_id, meta_list)

        return len(meta_list) - 1


def search(
    product_id:  str,
    query_emb:   np.ndarray,
    top_k:       int = 5,
) -> list[tuple[float, ImageEmbedding]]:
    """
    Find top-k most similar embeddings for a product.

    Returns:
        List of (score, ImageEmbedding) sorted by score descending.
        score in [0, 1] (cosine similarity via inner product on normalized vectors)
    """
    with _get_lock(product_id):
        index    = _load_index(product_id)
        meta_list = _load_meta(product_id)

        if index.ntotal == 0:
            return []

        k    = min(top_k, index.ntotal)
        emb  = _normalize(query_emb).reshape(1, -1)
        distances, indices = index.search(emb, k)

        results = []
        for score, idx in zip(distances[0], indices[0]):
            if idx < 0 or idx >= len(meta_list):
                continue
            results.append((float(score), ImageEmbedding.from_dict(meta_list[idx])))

        return results


def get_all_embeddings(product_id: str) -> tuple[np.ndarray, list[ImageEmbedding]]:
    """
    Return (matrix, metadata_list) for all stored embeddings of a product.
    matrix shape: (N, EMBEDDING_DIM). Returns empty arrays if no embeddings.
    """
    with _get_lock(product_id):
        index     = _load_index(product_id)
        meta_list = _load_meta(product_id)

        if index.ntotal == 0:
            return np.empty((0, EMBEDDING_DIM), dtype=np.float32), []

        try:
            import faiss
            matrix = faiss.rev_swig_ptr(index.get_xb(), index.ntotal * EMBEDDING_DIM)
            matrix = np.array(matrix).reshape(index.ntotal, EMBEDDING_DIM).copy()
        except Exception:
            matrix = np.empty((0, EMBEDDING_DIM), dtype=np.float32)

        meta_objects = [ImageEmbedding.from_dict(m) for m in meta_list]
        return matrix, meta_objects


def update_performance(
    product_id:        str,
    image_hash:        str,
    performance_score: float,
    clicks:            int   = 0,
    conversions:       int   = 0,
    revenue:           float = 0.0,
    updated_at:        str   = "",
) -> bool:
    """
    Update performance metadata for a stored embedding by image_hash.
    Returns True if found and updated, False if not found.
    """
    import datetime
    ts = updated_at or (datetime.datetime.now(datetime.timezone.utc).isoformat())

    with _get_lock(product_id):
        meta_list = _load_meta(product_id)
        found = False
        for m in meta_list:
            if m.get("image_hash") == image_hash:
                m["performance_score"] = round(performance_score, 8)
                m["clicks"]            = clicks
                m["conversions"]       = conversions
                m["revenue"]           = revenue
                m["performance_at"]    = ts
                found = True
                break

        if found:
            _save_meta(product_id, meta_list)
        return found


def count(product_id: str) -> int:
    """Number of embeddings stored for a product."""
    with _get_lock(product_id):
        return _load_index(product_id).ntotal


def list_products() -> list[str]:
    """All product_ids that have stored embeddings."""
    return [p.stem.replace(".meta", "") for p in _STORE_DIR.glob("*.meta.json")]


# ── FAISS helpers ─────────────────────────────────────────────────────────────

def _faiss_index():
    """Create new empty FAISS IndexFlatIP."""
    import faiss
    return faiss.IndexFlatIP(EMBEDDING_DIM)


def _index_path(product_id: str) -> Path:
    return _STORE_DIR / f"{product_id}.index"


def _meta_path(product_id: str) -> Path:
    return _STORE_DIR / f"{product_id}.meta.json"


def _load_index(product_id: str):
    import faiss
    p = _index_path(product_id)
    if p.exists():
        try:
            return faiss.read_index(str(p))
        except Exception:
            pass
    return _faiss_index()


def _save_index(product_id: str, index) -> None:
    import faiss
    faiss.write_index(index, str(_index_path(product_id)))


def _load_meta(product_id: str) -> list[dict]:
    p = _meta_path(product_id)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return []


def _save_meta(product_id: str, meta_list: list[dict]) -> None:
    _meta_path(product_id).write_text(json.dumps(meta_list, ensure_ascii=False, indent=2))


def _normalize(emb: np.ndarray) -> np.ndarray:
    """L2-normalize embedding vector."""
    norm = np.linalg.norm(emb)
    if norm < 1e-8:
        return emb
    return (emb / norm).astype(np.float32)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--count",   metavar="PRODUCT_ID")
    parser.add_argument("--list",    action="store_true")
    args = parser.parse_args()

    if args.count:
        print(f"{args.count}: {count(args.count)} embeddings")
    elif args.list:
        products = list_products()
        for pid in products:
            print(f"  {pid}: {count(pid)} embeddings")
        if not products:
            print("  (no products in vector store)")

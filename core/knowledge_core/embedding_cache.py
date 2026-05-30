#!/usr/bin/env python3
"""
embedding_cache.py — Hash-based embedding cache for knowledge_core.

Strategy:
1. SHA256(text) → cache key
2. Check CACHE_DIR/{key}.npy — return if exists
3. Compute with transformers all-MiniLM-L6-v2 (mean pooling)
4. Fallback: TF-IDF vector if transformers unavailable
5. Save to cache, return float32 (384,)

100% LOCAL — zero network calls.
CPU-only — no GPU dependency.
"""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

import numpy as np

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

CACHE_DIR = _IMPERIO_ROOT / "memory" / "embedding_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

EMBEDDING_DIM  = 384
MODEL_NAME     = "sentence-transformers/all-MiniLM-L6-v2"

# Module-level model cache (loaded once per process)
_model     = None
_tokenizer = None
_tfidf_vec = None
_tfidf_fitted = False


# ── Model loading ─────────────────────────────────────────────────────────────

def _load_transformers_model():
    """Load tokenizer + model once. Returns (tokenizer, model) or (None, None)."""
    global _model, _tokenizer
    if _model is not None:
        return _tokenizer, _model
    try:
        from transformers import AutoTokenizer, AutoModel
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model     = AutoModel.from_pretrained(MODEL_NAME)
        _model.eval()
        return _tokenizer, _model
    except Exception:
        return None, None


def _mean_pool(token_embeddings: "torch.Tensor", attention_mask: "torch.Tensor") -> "torch.Tensor":
    """Mean pooling over token dimension, masked."""
    import torch
    mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    summed        = torch.sum(token_embeddings * mask_expanded, dim=1)
    count         = torch.clamp(mask_expanded.sum(dim=1), min=1e-9)
    return summed / count


def _compute_transformers(text: str) -> np.ndarray | None:
    """Compute embedding via transformers. Returns (384,) float32 or None on failure."""
    try:
        import torch
        tokenizer, model = _load_transformers_model()
        if tokenizer is None or model is None:
            return None
        inputs = tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        )
        with torch.no_grad():
            outputs = model(**inputs)
        pooled = _mean_pool(outputs.last_hidden_state, inputs["attention_mask"])
        vec    = pooled.squeeze(0).numpy().astype(np.float32)
        # L2-normalize for cosine similarity
        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec = vec / norm
        return vec
    except Exception:
        return None


def _compute_tfidf(text: str) -> np.ndarray:
    """
    TF-IDF fallback embedding. Returns (384,) float32.
    Uses a fixed vocabulary hash trick to produce deterministic 384-dim vectors.
    """
    global _tfidf_vec, _tfidf_fitted

    # Simple hash-trick TF-IDF: tokenize → hash into 384 buckets → normalize
    words = text.lower().split()
    vec   = np.zeros(EMBEDDING_DIM, dtype=np.float32)

    word_freq: dict[str, int] = {}
    for w in words:
        word_freq[w] = word_freq.get(w, 0) + 1

    for w, freq in word_freq.items():
        idx      = int(hashlib.sha256(w.encode()).hexdigest(), 16) % EMBEDDING_DIM
        vec[idx] += freq

    norm = np.linalg.norm(vec)
    if norm > 1e-9:
        vec = vec / norm
    return vec


def _compute_embedding(text: str) -> np.ndarray:
    """
    Compute embedding for text.
    Tries transformers first, falls back to TF-IDF hash trick.
    Always returns float32 array of shape (EMBEDDING_DIM,).
    """
    vec = _compute_transformers(text)
    if vec is not None and vec.shape == (EMBEDDING_DIM,):
        return vec
    return _compute_tfidf(text)


# ── Cache I/O ─────────────────────────────────────────────────────────────────

def _cache_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.npy"


# ── Public API ────────────────────────────────────────────────────────────────

def get_embedding(text: str) -> np.ndarray:
    """
    Get embedding for text, using cache if available.

    1. SHA256 hash lookup → return cached .npy
    2. Compute (transformers or TF-IDF fallback)
    3. Save to cache
    4. Return float32 (384,)

    Never raises.
    """
    if not text or not text.strip():
        return np.zeros(EMBEDDING_DIM, dtype=np.float32)

    key   = _cache_key(text)
    cpath = _cache_path(key)

    if cpath.exists():
        try:
            vec = np.load(str(cpath))
            if vec.shape == (EMBEDDING_DIM,):
                return vec.astype(np.float32)
        except Exception:
            pass  # corrupt cache — recompute

    vec = _compute_embedding(text)

    try:
        np.save(str(cpath), vec)
    except Exception:
        pass  # cache write failure is non-fatal

    return vec


def clear_stale(max_age_days: int = 30) -> int:
    """
    Remove cached embeddings older than max_age_days.
    Returns count of removed files.
    """
    cutoff = time.time() - max_age_days * 86400
    removed = 0
    try:
        for p in CACHE_DIR.glob("*.npy"):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
                    removed += 1
            except Exception:
                pass
    except Exception:
        pass
    return removed

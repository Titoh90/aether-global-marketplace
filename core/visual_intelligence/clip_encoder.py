#!/usr/bin/env python3
"""
clip_encoder.py — CLIP image encoder with caching and MPS acceleration.

Model: ViT-B/32 via open_clip (frozen weights, inference only)
Device: MPS (Apple Silicon) → CUDA → CPU (auto-detect)
Cache: sha256(image_bytes) → embedding stored on disk to avoid re-encoding

Fallback: if open_clip unavailable → histogram_encoder (color distribution)
  Histogram fallback produces 512D vectors via color histogram + texture stats.
  Less semantically powerful, but enables the pipeline to run without torch deps.

ZERO writes to Truth Layer. ZERO AI calls during encoding.
Embeddings stored to core/visual_intelligence cache, not production logs.
"""

from __future__ import annotations

import hashlib
import json
import sys
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

_CACHE_DIR = _IMPERIO_ROOT / "logs" / "visual_intelligence" / "embedding_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants ─────────────────────────────────────────────────────────────────

EMBEDDING_DIM   = 512
_CLIP_MODEL     = "ViT-B-32"
_CLIP_PRETRAIN  = "openai"

# Module-level singletons (lazy-loaded)
_clip_model     = None
_clip_preprocess = None
_clip_device    = None
_clip_available = None   # None = not yet checked


# ── Public API ────────────────────────────────────────────────────────────────

def encode_image(image_bytes: bytes) -> tuple[np.ndarray, str]:
    """
    Encode image bytes → 512D float32 embedding vector.

    Returns:
        (embedding: np.ndarray shape (512,), model_name: str)

    Uses disk cache keyed by sha256(image_bytes).
    Never raises — falls back to histogram encoder on any failure.
    """
    img_hash = _hash_image(image_bytes)

    # Check cache first
    cached = _load_cache(img_hash)
    if cached is not None:
        return cached, _get_model_name()

    try:
        if _is_clip_available():
            emb = _encode_clip(image_bytes)
            model_name = f"{_CLIP_MODEL}/{_CLIP_PRETRAIN}"
        else:
            emb = _encode_histogram(image_bytes)
            model_name = "histogram_fallback"

        _save_cache(img_hash, emb)
        return emb, model_name

    except Exception:
        emb = _encode_histogram(image_bytes)
        _save_cache(img_hash, emb)
        return emb, "histogram_fallback"


def encode_image_file(path: Path) -> tuple[np.ndarray, str]:
    """Convenience: encode from file path."""
    return encode_image(path.read_bytes())


def image_hash(image_bytes: bytes) -> str:
    """sha256[:16] of image bytes — use as cache key."""
    return _hash_image(image_bytes)


# ── CLIP encoder ─────────────────────────────────────────────────────────────

def _is_clip_available() -> bool:
    global _clip_available
    if _clip_available is not None:
        return _clip_available
    try:
        import open_clip  # noqa: F401
        _clip_available = True
    except ImportError:
        _clip_available = False
    return _clip_available


def _get_model_name() -> str:
    if _is_clip_available():
        return f"{_CLIP_MODEL}/{_CLIP_PRETRAIN}"
    return "histogram_fallback"


def _load_clip() -> None:
    """Lazy-load CLIP model. Runs once per process."""
    global _clip_model, _clip_preprocess, _clip_device

    if _clip_model is not None:
        return

    import open_clip
    import torch

    # Device priority: MPS → CUDA → CPU
    if torch.backends.mps.is_available():
        _clip_device = "mps"
    elif torch.cuda.is_available():
        _clip_device = "cuda"
    else:
        _clip_device = "cpu"

    _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
        _CLIP_MODEL, pretrained=_CLIP_PRETRAIN, device=_clip_device
    )
    _clip_model.eval()


def _encode_clip(image_bytes: bytes) -> np.ndarray:
    """Encode using CLIP ViT-B/32. Returns (512,) float32."""
    import open_clip
    import torch
    from PIL import Image

    _load_clip()

    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    tensor = _clip_preprocess(img).unsqueeze(0).to(_clip_device)

    with torch.no_grad():
        features = _clip_model.encode_image(tensor)
        features = features / features.norm(dim=-1, keepdim=True)  # L2 normalize

    emb = features.squeeze(0).cpu().numpy().astype(np.float32)
    assert emb.shape == (EMBEDDING_DIM,), f"Unexpected shape: {emb.shape}"
    return emb


# ── Histogram fallback encoder ─────────────────────────────────────────────────

def _encode_histogram(image_bytes: bytes) -> np.ndarray:
    """
    Fallback encoder using color histograms + basic texture statistics.
    Produces 512D vector without CLIP dependency.

    Breakdown:
      - 256 bins R histogram (normalized)
      - 128 bins G histogram (normalized)
      - 128 bins B histogram (normalized)
      = 512D
    """
    try:
        from PIL import Image
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        img = img.resize((128, 128))
        arr = np.array(img, dtype=np.float32)

        r_hist = np.histogram(arr[:, :, 0], bins=256, range=(0, 256))[0].astype(np.float32)
        g_hist = np.histogram(arr[:, :, 1], bins=128, range=(0, 256))[0].astype(np.float32)
        b_hist = np.histogram(arr[:, :, 2], bins=128, range=(0, 256))[0].astype(np.float32)

        # Normalize each
        r_hist /= (r_hist.sum() + 1e-8)
        g_hist /= (g_hist.sum() + 1e-8)
        b_hist /= (b_hist.sum() + 1e-8)

        emb = np.concatenate([r_hist, g_hist, b_hist]).astype(np.float32)
        assert emb.shape == (512,)
        return emb

    except Exception:
        return np.zeros(EMBEDDING_DIM, dtype=np.float32)


# ── Cache ─────────────────────────────────────────────────────────────────────

def _hash_image(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()[:16]


def _cache_path(img_hash: str) -> Path:
    return _CACHE_DIR / f"{img_hash}.npy"


def _load_cache(img_hash: str) -> Optional[np.ndarray]:
    p = _cache_path(img_hash)
    if p.exists():
        try:
            return np.load(str(p))
        except Exception:
            pass
    return None


def _save_cache(img_hash: str, emb: np.ndarray) -> None:
    try:
        np.save(str(_cache_path(img_hash)), emb)
    except Exception:
        pass


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True, help="Path to image file")
    args = parser.parse_args()

    path = Path(args.image)
    emb, model = encode_image_file(path)
    print(f"Model:  {model}")
    print(f"Shape:  {emb.shape}")
    print(f"Norm:   {np.linalg.norm(emb):.4f}")
    print(f"Sample: {emb[:8]}")

#!/usr/bin/env python3
"""
archetype_engine.py — Discover visual style clusters from stored embeddings.

Algorithm:
    KMeans on CLIP embeddings → cluster centroids
    Rank clusters by mean performance_score of members
    Label each cluster with a template name: {STYLE}_{idx:02d}

Operating modes (enforced):
    < MIN_SAMPLES_FOR_CLUSTERING → return empty list (not enough data yet)
    >= MIN_SAMPLES_FOR_CLUSTERING → run KMeans, return VisualArchetype list

Cluster count: min(n_embeddings // 5, MAX_CLUSTERS) — scales with data
MAX_CLUSTERS: 8 (beyond this, archetypes lose distinctiveness)

Offline batch — never called in real-time posting path.
ZERO AI calls. Pure numpy KMeans.
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path
from typing import Optional

import numpy as np

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.visual_intelligence import MIN_SAMPLES_FOR_CLUSTERING
from core.visual_intelligence.schemas import VisualArchetype, ImageEmbedding

MAX_CLUSTERS   = 8
_ARCHETYPE_DIR = _IMPERIO_ROOT / "logs" / "visual_intelligence" / "archetypes"
_ARCHETYPE_DIR.mkdir(parents=True, exist_ok=True)

# Label templates — assigned round-robin to clusters (ranked by performance)
_STYLE_LABELS = [
    "PREMIUM_MINIMAL_STUDIO",
    "DARK_LUXURY_CINEMATIC",
    "COLORFUL_LIFESTYLE_UGC",
    "CLEAN_WHITE_EDITORIAL",
    "WARM_EMOTIONAL_NATURAL",
    "BOLD_HIGH_CONTRAST_IMPACT",
    "SOFT_AESTHETIC_PASTEL",
    "RAW_AUTHENTIC_HANDHELD",
]

# Prompt injection templates per label
_PROMPT_BIAS: dict[str, str] = {
    "PREMIUM_MINIMAL_STUDIO":     "premium minimal studio, white background, soft shadows, clean product hero shot",
    "DARK_LUXURY_CINEMATIC":      "dark luxury cinematic, deep shadows, rim light, anamorphic bokeh, premium product",
    "COLORFUL_LIFESTYLE_UGC":     "colorful lifestyle UGC style, natural light, authentic environment, vibrant energy",
    "CLEAN_WHITE_EDITORIAL":      "clean white editorial, high-key lighting, magazine quality, sharp product detail",
    "WARM_EMOTIONAL_NATURAL":     "warm emotional natural light, golden hour, soft depth of field, lifestyle feeling",
    "BOLD_HIGH_CONTRAST_IMPACT":  "bold high contrast, dramatic lighting, strong shadows, impactful composition",
    "SOFT_AESTHETIC_PASTEL":      "soft aesthetic pastel tones, delicate shadows, ethereal quality, dreamy atmosphere",
    "RAW_AUTHENTIC_HANDHELD":     "authentic handheld style, candid energy, real-world context, unfiltered feel",
}


# ── Public API ────────────────────────────────────────────────────────────────

def compute_archetypes(product_id: str) -> list[VisualArchetype]:
    """
    Discover visual archetypes for a product from stored embeddings.

    Returns:
        List of VisualArchetype sorted by avg_performance descending.
        Empty list if insufficient data (< MIN_SAMPLES_FOR_CLUSTERING).
    """
    from core.visual_intelligence import vector_store

    matrix, meta_objects = vector_store.get_all_embeddings(product_id)

    if len(meta_objects) < MIN_SAMPLES_FOR_CLUSTERING:
        return []

    n_clusters = min(len(meta_objects) // 5, MAX_CLUSTERS)
    n_clusters = max(n_clusters, 2)   # minimum 2 clusters

    labels = _kmeans(matrix, n_clusters)
    archetypes = _build_archetypes(product_id, matrix, meta_objects, labels, n_clusters)

    # Sort by new ranking formula (replaces plain avg_performance sort)
    total_embs = len(meta_objects)
    archetypes.sort(key=lambda a: _rank_score(a, total_embs), reverse=True)

    # Persist
    _save_archetypes(product_id, archetypes)
    return archetypes


def get_best_archetype(product_id: str) -> Optional[VisualArchetype]:
    """
    Return top-performing archetype for a product (from cached computation).
    Returns None if not enough data or no archetypes computed yet.
    """
    archetypes = _load_archetypes(product_id)
    if not archetypes:
        return None
    return archetypes[0]


def get_prompt_bias(label: str) -> str:
    """Return Flow prompt injection text for a given archetype label."""
    return _PROMPT_BIAS.get(label, "")


def get_category_centroid(product_id: str) -> Optional[np.ndarray]:
    """
    Return the mean embedding vector for all stored embeddings of a product.

    Returns None if no embeddings available or on failure.
    Never raises.
    """
    try:
        from core.visual_intelligence import vector_store
        matrix, _ = vector_store.get_all_embeddings(product_id)
        if matrix.shape[0] == 0:
            return None
        centroid = matrix.mean(axis=0)
        norm = np.linalg.norm(centroid)
        if norm > 1e-8:
            centroid = centroid / norm
        return centroid.astype(np.float32)
    except Exception as e:
        print(f"[archetype_engine] WARNING: get_category_centroid failed for '{product_id}': {e}")
        return None


# ── Ranking ───────────────────────────────────────────────────────────────────

def _rank_score(archetype: "VisualArchetype", total_embeddings: int) -> float:
    """
    Composite ranking score for sorting archetypes.

    final_score = 0.35*revenue_score + 0.30*similarity_score + 0.20*recency_score + 0.15*stability_score

    - revenue_score:    normalized avg_performance (0-1, capped)
    - similarity_score: cluster_size relative to total embeddings
    - recency_score:    1.0 (placeholder — future: decay by days_since_last_post)
    - stability_score:  cluster cohesion proxy (larger clusters more stable)
    """
    revenue_score    = min(archetype.avg_performance, 1.0)
    similarity_score = min(archetype.cluster_size / max(total_embeddings, 1), 1.0)
    recency_score    = 1.0
    stability_score  = min(archetype.cluster_size / 5, 1.0)

    return (0.35 * revenue_score +
            0.30 * similarity_score +
            0.20 * recency_score +
            0.15 * stability_score)


# ── KMeans (pure numpy) ───────────────────────────────────────────────────────

def _kmeans(matrix: np.ndarray, k: int, max_iter: int = 100) -> np.ndarray:
    """
    Pure numpy KMeans. No sklearn dependency.
    Returns label array shape (N,) with cluster indices 0..k-1.
    """
    n = len(matrix)
    if n < k:
        return np.zeros(n, dtype=int)

    # Random init from data points
    rng = np.random.default_rng(42)
    centroid_indices = rng.choice(n, size=k, replace=False)
    centroids = matrix[centroid_indices].copy()

    labels = np.zeros(n, dtype=int)

    for _ in range(max_iter):
        # Assign step: cosine similarity via dot product (vectors are L2-normalized)
        sims    = matrix @ centroids.T   # shape (N, k)
        new_labels = np.argmax(sims, axis=1)

        if np.array_equal(new_labels, labels):
            break
        labels = new_labels

        # Update step
        for c in range(k):
            members = matrix[labels == c]
            if len(members) > 0:
                centroid = members.mean(axis=0)
                norm = np.linalg.norm(centroid)
                centroids[c] = centroid / (norm + 1e-8)

    return labels


# ── Build VisualArchetype objects ─────────────────────────────────────────────

def _build_archetypes(
    product_id:   str,
    matrix:       np.ndarray,
    meta_objects: list[ImageEmbedding],
    labels:       np.ndarray,
    n_clusters:   int,
) -> list[VisualArchetype]:
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    archetypes = []

    for c in range(n_clusters):
        member_indices = np.where(labels == c)[0]
        if len(member_indices) == 0:
            continue

        members = [meta_objects[i] for i in member_indices]
        scores  = [m.performance_score for m in members]
        avg_perf = sum(scores) / len(scores)

        # Top posts = highest performing in cluster
        sorted_members = sorted(members, key=lambda m: m.performance_score, reverse=True)
        top_post_ids   = tuple(m.post_id for m in sorted_members[:3])

        archetype_id = f"ARCHETYPE_{product_id}_{c:02d}"
        # Label assigned after sorting by performance (done in caller)
        label = _STYLE_LABELS[c % len(_STYLE_LABELS)]

        archetypes.append(VisualArchetype(
            archetype_id=archetype_id,
            product_id=product_id,
            label=label,
            cluster_size=len(members),
            avg_performance=avg_perf,
            centroid_summary=_PROMPT_BIAS.get(label, ""),
            top_post_ids=top_post_ids,
            created_at=ts,
        ))

    return archetypes


# ── Persistence ───────────────────────────────────────────────────────────────

def _archetypes_path(product_id: str) -> Path:
    return _ARCHETYPE_DIR / f"{product_id}.json"


def _save_archetypes(product_id: str, archetypes: list[VisualArchetype]) -> None:
    data = [a.to_dict() for a in archetypes]
    _archetypes_path(product_id).write_text(json.dumps(data, indent=2))


def _load_archetypes(product_id: str) -> list[VisualArchetype]:
    p = _archetypes_path(product_id)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
        return [
            VisualArchetype(
                archetype_id=d["archetype_id"],
                product_id=d["product_id"],
                label=d["label"],
                cluster_size=d["cluster_size"],
                avg_performance=d["avg_performance"],
                centroid_summary=d["centroid_summary"],
                top_post_ids=tuple(d["top_post_ids"]),
                created_at=d["created_at"],
            )
            for d in data
        ]
    except Exception:
        return []


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--compute", metavar="PRODUCT_ID")
    parser.add_argument("--best",    metavar="PRODUCT_ID")
    args = parser.parse_args()

    if args.compute:
        archetypes = compute_archetypes(args.compute)
        if archetypes:
            for a in archetypes:
                print(json.dumps(a.to_dict(), indent=2))
        else:
            print(f"Not enough data (<{MIN_SAMPLES_FOR_CLUSTERING} embeddings)")
    elif args.best:
        a = get_best_archetype(args.best)
        if a:
            print(json.dumps(a.to_dict(), indent=2))
        else:
            print("No archetypes computed yet")

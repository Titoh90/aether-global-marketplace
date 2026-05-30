#!/usr/bin/env python3
"""
archetype_memory.py — Persistent category-scoped archetype memory.

Stores visual archetypes per product category (not per product_id).
Applies daily decay to keep scores fresh.
Never deletes archetypes — only transitions status: active → degraded → archived.

OFFLINE ONLY. No internet. No API calls.
"""

from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import numpy as np

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

DAILY_DECAY          = 0.995
DEGRADED_THRESHOLD   = 0.4
ARCHIVED_THRESHOLD   = 0.2

_MEMORY_DIR = _IMPERIO_ROOT / "logs" / "visual_intelligence" / "archetype_memory"
_MEMORY_DIR.mkdir(parents=True, exist_ok=True)

# Cold-start gate: need at least 20 embeddings in vector_store for a category
_MIN_EMBEDDINGS_FOR_MEMORY = 20


# ── Public API ────────────────────────────────────────────────────────────────

def get_archetypes(category: str) -> list[dict]:
    """
    Load archetypes for a category and apply daily decay.

    Returns empty list on cold start (< _MIN_EMBEDDINGS_FOR_MEMORY in vector_store)
    or on any failure. Never raises.
    """
    try:
        if not _has_enough_embeddings(category):
            return []

        archetypes = _load_raw(category)
        if not archetypes:
            return []

        now = datetime.datetime.now(datetime.timezone.utc)
        updated = []
        for arch in archetypes:
            try:
                last_seen_str = arch.get("last_seen", "")
                if last_seen_str:
                    last_seen = datetime.datetime.fromisoformat(last_seen_str.rstrip("Z"))
                    days_elapsed = max((now - last_seen).total_seconds() / 86400.0, 0.0)
                else:
                    days_elapsed = 1.0
                arch = apply_decay([arch], days_elapsed=days_elapsed)[0]
                arch = transition_status(arch)
            except Exception as e:
                print(f"[archetype_memory] WARNING: decay failed for archetype: {e}")
            updated.append(arch)
        return updated
    except Exception as e:
        print(f"[archetype_memory] WARNING: get_archetypes failed for '{category}': {e}")
        return []


def save_archetypes(category: str, archetypes: list[dict]) -> None:
    """
    Persist archetypes for a category to disk.
    Never raises.
    """
    try:
        _MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "category": category,
            "archetypes": archetypes,
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        _category_path(category).write_text(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"[archetype_memory] WARNING: save_archetypes failed for '{category}': {e}")


def upsert_archetype(
    category:     str,
    name:         str,
    style_labels: list[str],
    centroid:     np.ndarray,
    revenue:      float,
    similarity:   float,
) -> None:
    """
    Add a new archetype or update an existing one by name.

    Updates:
    - avg_similarity (running average)
    - avg_revenue (running average)
    - usage_count
    - last_seen
    - embedding_centroid (running mean)

    Never raises.
    """
    try:
        archetypes = _load_raw(category)
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Find existing
        existing = next((a for a in archetypes if a.get("name") == name), None)

        if existing is not None:
            idx = archetypes.index(existing)
            count = existing.get("usage_count", 1)
            new_count = count + 1

            # Running averages
            old_sim = existing.get("avg_similarity", similarity)
            new_sim = (old_sim * count + similarity) / new_count

            old_rev = existing.get("avg_revenue", revenue)
            new_rev = (old_rev * count + revenue) / new_count

            # Running centroid mean
            old_centroid = np.array(existing.get("embedding_centroid", centroid.tolist()), dtype=np.float32)
            new_centroid = (old_centroid * count + centroid) / new_count

            # Successful post?
            last_success = existing.get("last_success", "")
            if revenue > 0:
                last_success = now_str

            updated = dict(existing)
            updated.update({
                "style_labels":       style_labels,
                "embedding_centroid": new_centroid.tolist(),
                "avg_similarity":     round(float(new_sim), 6),
                "avg_revenue":        round(float(new_rev), 6),
                "usage_count":        new_count,
                "last_seen":          now_str,
                "last_success":       last_success,
            })
            updated = transition_status(updated)
            archetypes[idx] = updated
        else:
            new_arch = {
                "name":               name,
                "style_labels":       style_labels,
                "embedding_centroid": centroid.tolist(),
                "avg_similarity":     round(float(similarity), 6),
                "conversion_rate":    0.0,
                "avg_revenue":        round(float(revenue), 6),
                "usage_count":        1,
                "last_seen":          now_str,
                "last_success":       now_str if revenue > 0 else "",
                "decay_factor":       DAILY_DECAY,
                "status":             "active",
            }
            archetypes.append(new_arch)

        save_archetypes(category, archetypes)
    except Exception as e:
        print(f"[archetype_memory] WARNING: upsert_archetype failed for '{category}/{name}': {e}")


def apply_decay(archetypes: list[dict], days_elapsed: float = 1.0) -> list[dict]:
    """
    Apply decay to avg_similarity scores.

    score = avg_similarity * (decay_factor ** days_elapsed)

    Returns new list — does NOT mutate input dicts.
    Never raises.
    """
    try:
        result = []
        for arch in archetypes:
            try:
                decay_factor = float(arch.get("decay_factor", DAILY_DECAY))
                old_sim = float(arch.get("avg_similarity", 0.0))
                new_sim = old_sim * (decay_factor ** days_elapsed)
                updated = dict(arch)
                updated["avg_similarity"] = round(new_sim, 8)
                result.append(updated)
            except Exception as e:
                print(f"[archetype_memory] WARNING: decay failed for one archetype: {e}")
                result.append(arch)
        return result
    except Exception as e:
        print(f"[archetype_memory] WARNING: apply_decay failed: {e}")
        return archetypes


def transition_status(archetype: dict) -> dict:
    """
    Transition archetype status based on avg_similarity thresholds.

    active    → degraded  if avg_similarity < DEGRADED_THRESHOLD (0.4)
    degraded  → archived  if avg_similarity < ARCHIVED_THRESHOLD (0.2)
    archived  → (stays archived — never upgraded automatically)

    Returns updated dict (does NOT mutate input).
    Never raises.
    """
    try:
        updated = dict(archetype)
        sim = float(updated.get("avg_similarity", 0.0))
        current_status = updated.get("status", "active")

        if current_status == "archived":
            return updated  # already at terminal state

        if sim < ARCHIVED_THRESHOLD and current_status == "degraded":
            updated["status"] = "archived"
        elif sim < DEGRADED_THRESHOLD and current_status == "active":
            updated["status"] = "degraded"

        return updated
    except Exception as e:
        print(f"[archetype_memory] WARNING: transition_status failed: {e}")
        return archetype


# ── Internal helpers ──────────────────────────────────────────────────────────

def _category_path(category: str) -> Path:
    safe = category.replace("/", "_").replace("\\", "_")
    return _MEMORY_DIR / f"{safe}.json"


def _load_raw(category: str) -> list[dict]:
    """Load raw archetypes list from disk. Returns [] on missing/corrupt file."""
    p = _category_path(category)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
        archetypes = data.get("archetypes", [])
        if not isinstance(archetypes, list):
            return []
        return archetypes
    except Exception as e:
        print(f"[archetype_memory] WARNING: corrupted JSON for '{category}': {e}")
        return []


def _has_enough_embeddings(category: str) -> bool:
    """
    Check if there are enough embeddings in the vector_store for this category.
    Uses product_id = category as a proxy (cold start gate).
    Returns True if count >= _MIN_EMBEDDINGS_FOR_MEMORY OR if file already exists.
    """
    # If we already have a memory file, don't gate
    if _category_path(category).exists():
        return True

    try:
        from core.visual_intelligence import vector_store
        count = vector_store.count(category)
        return count >= _MIN_EMBEDDINGS_FOR_MEMORY
    except Exception:
        # If vector_store is unavailable, allow (don't gate on missing dependency)
        return True

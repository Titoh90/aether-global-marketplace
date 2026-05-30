#!/usr/bin/env python3
"""
continuity_score_tracker.py — Persistent continuity score tracking.

Records continuity scores across sandbox experiments to identify
which prompt patterns, shot types, and transition choices consistently
produce better continuity. Feeds back into the variation engine.

Persistent JSON storage in logs/sandbox/continuity/.
Across sessions, the agent learns empirically — not just from specs.

Teaches the agent: "History tells you what works. Don't guess."

SANDBOX-ONLY: Never touches production pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path

from core.cinematic_video.sandbox.schemas import (
    ContinuityRecord,
    _make_id,
    _now_iso,
)


_IMPERIO_ROOT = Path(__file__).parent.parent.parent.parent
_STORE_DIR = _IMPERIO_ROOT / "logs" / "sandbox" / "continuity"
_STORE_FILE = _STORE_DIR / "scores.jsonl"


def _ensure_store() -> None:
    _STORE_DIR.mkdir(parents=True, exist_ok=True)


def _load_all() -> list[dict]:
    """Load all continuity records from disk."""
    if not _STORE_FILE.exists():
        return []
    records: list[dict] = []
    try:
        for line in _STORE_FILE.read_text().strip().split("\n"):
            if line.strip():
                records.append(json.loads(line))
    except Exception:
        return []
    return records


def _append_record(record: ContinuityRecord) -> None:
    """Append one record to the JSONL store."""
    _ensure_store()
    try:
        with open(_STORE_FILE, "a") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    except Exception:
        pass  # Never raise — silently fail if disk is unwritable


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def record_continuity_score(
    variation_id: str,
    dimension: str,
    score: float,
    experiment_id: str = "",
    notes: str = "",
) -> ContinuityRecord:
    """
    Record a continuity score for a variation.

    Never raises — returns record even if persistence fails.
    """
    rec = ContinuityRecord(
        record_id=_make_id("cont"),
        variation_id=variation_id,
        dimension=dimension,
        score=round(min(max(score, 0.0), 1.0), 3),
        recorded_at=_now_iso(),
        experiment_id=experiment_id,
        notes=notes,
    )
    _append_record(rec)
    return rec


def get_continuity_history(
    dimension: str = "",
    min_score: float = 0.0,
    limit: int = 100,
) -> tuple[ContinuityRecord, ...]:
    """
    Retrieve continuity history, optionally filtered by dimension.

    Returns most recent records first.
    """
    all_data = _load_all()
    records: list[ContinuityRecord] = []

    for d in all_data[::-1]:  # Most recent first
        if dimension and d.get("dimension") != dimension:
            continue
        if d.get("score", 0) < min_score:
            continue
        records.append(ContinuityRecord(
            record_id=d.get("record_id", ""),
            variation_id=d.get("variation_id", ""),
            dimension=d.get("dimension", ""),
            score=d.get("score", 0),
            recorded_at=d.get("recorded_at", ""),
            experiment_id=d.get("experiment_id", ""),
            notes=d.get("notes", ""),
        ))
        if len(records) >= limit:
            break

    return tuple(records)


def get_best_patterns(
    top_n: int = 5,
) -> tuple[dict, ...]:
    """
    Identify the best-performing variation patterns across all dimensions.

    Returns top N (variation_id, avg_score, dimension, count).
    """
    all_data = _load_all()

    # Aggregate by variation_id
    agg: dict[str, dict] = {}
    for d in all_data:
        vid = d.get("variation_id", "")
        if vid not in agg:
            agg[vid] = {"scores": [], "dimensions": set(), "count": 0}
        agg[vid]["scores"].append(d.get("score", 0))
        agg[vid]["dimensions"].add(d.get("dimension", ""))
        agg[vid]["count"] += 1

    # Sort by average score
    ranked = []
    for vid, data in agg.items():
        avg = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
        ranked.append({
            "variation_id": vid,
            "avg_score": round(avg, 3),
            "dimensions": sorted(data["dimensions"]),
            "sample_count": data["count"],
        })

    ranked.sort(key=lambda x: x["avg_score"], reverse=True)
    return tuple(ranked[:top_n])


def get_dimension_trend(
    dimension: str,
    lookback: int = 20,
) -> dict:
    """
    Get the score trend for a specific continuity dimension.

    Returns dict with: dimension, recent_scores, avg, trend ("improving" | "stable" | "declining").
    """
    records = get_continuity_history(dimension=dimension, limit=lookback)
    if not records:
        return {"dimension": dimension, "recent_scores": (), "avg": 0.0, "trend": "stable"}

    scores = [r.score for r in records]
    avg = sum(scores) / len(scores)

    if len(scores) >= 4:
        first_half = sum(scores[:len(scores)//2]) / (len(scores)//2)
        second_half = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
        if second_half > first_half + 0.05:
            trend = "improving"
        elif second_half < first_half - 0.05:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "stable"

    return {
        "dimension": dimension,
        "recent_scores": tuple(scores),
        "avg": round(avg, 3),
        "trend": trend,
    }


def clear_continuity_history() -> bool:
    """Clear all continuity records. Returns True if successful."""
    try:
        if _STORE_FILE.exists():
            _STORE_FILE.unlink()
        return True
    except Exception:
        return False


__all__ = [
    "record_continuity_score",
    "get_continuity_history",
    "get_best_patterns",
    "get_dimension_trend",
    "clear_continuity_history",
]

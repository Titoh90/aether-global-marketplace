#!/usr/bin/env python3
"""
drift_detector.py — Detect visual quality degradation and archetype revenue drift.

DRIFT TYPE 1: Flow Quality Drift
    rolling_similarity_7d < rolling_similarity_30d * 0.82 → "high" severity

DRIFT TYPE 2: Archetype Revenue Drift
    current_ctr < historical_ctr * 0.45 → set status="degraded"

DRIFT TYPE 3: Category Visual Shift
    cosine distance between current centroid vs 30d-ago centroid > threshold

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

_LOG_DIR = _IMPERIO_ROOT / "logs" / "visual_drift"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# Drift thresholds
_FLOW_QUALITY_RATIO    = 0.82   # 7d rolling < 30d * 0.82 → high severity
_REVENUE_DRIFT_RATIO   = 0.45   # current_ctr < historical_ctr * 0.45 → degraded
_CATEGORY_SHIFT_DEFAULT = 0.15  # cosine distance threshold


# ── Public API ────────────────────────────────────────────────────────────────

def detect_flow_quality_drift(
    category:             str,
    recent_similarities:  list[float],
    baseline_similarities: list[float],
) -> dict | None:
    """
    Detect if recent Flow output quality has dropped versus baseline.

    Args:
        category:             product category tag
        recent_similarities:  last 7-day similarity scores (list of floats 0-1)
        baseline_similarities: last 30-day similarity scores (list of floats 0-1)

    Returns:
        drift event dict if drift detected, None otherwise.
    Never raises.
    """
    try:
        if not recent_similarities or not baseline_similarities:
            return None

        rolling_7d  = float(np.mean(recent_similarities))
        rolling_30d = float(np.mean(baseline_similarities))

        if rolling_30d < 1e-8:
            return None

        if rolling_7d < rolling_30d * _FLOW_QUALITY_RATIO:
            event = {
                "type":               "flow_quality_drift",
                "category":           category,
                "severity":           "high",
                "current_similarity": round(rolling_7d, 6),
                "baseline_similarity": round(rolling_30d, 6),
                "ratio":              round(rolling_7d / rolling_30d, 4),
                "threshold_ratio":    _FLOW_QUALITY_RATIO,
                "detected_at":        datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            _log_event(event)
            return event

        return None
    except Exception as e:
        print(f"[drift_detector] WARNING: detect_flow_quality_drift failed: {e}")
        return None


def detect_revenue_drift(
    category:        str,
    archetypes:      list[dict],
    current_metrics: dict,
) -> list[dict]:
    """
    Detect archetypes whose CTR has dropped below historical levels.

    Args:
        category:        product category
        archetypes:      list of archetype dicts (from archetype_memory)
        current_metrics: dict mapping archetype name → {"ctr": float, ...}

    Returns:
        List of degraded archetype dicts (updated status="degraded").
        Empty list if no drift detected or on failure.
    Never raises.
    """
    try:
        degraded = []
        for arch in archetypes:
            try:
                name = arch.get("name", "")
                if not name:
                    continue

                historical_ctr = float(arch.get("conversion_rate", 0.0))
                if historical_ctr < 1e-8:
                    # No historical baseline — skip
                    continue

                metrics = current_metrics.get(name, {})
                current_ctr = float(metrics.get("ctr", 0.0))

                if current_ctr < historical_ctr * _REVENUE_DRIFT_RATIO:
                    updated = dict(arch)
                    updated["status"] = "degraded"

                    event = {
                        "type":            "archetype_revenue_drift",
                        "category":        category,
                        "archetype_name":  name,
                        "current_ctr":     round(current_ctr, 6),
                        "historical_ctr":  round(historical_ctr, 6),
                        "ratio":           round(current_ctr / historical_ctr, 4),
                        "threshold_ratio": _REVENUE_DRIFT_RATIO,
                        "action":          "set_degraded",
                        "detected_at":     datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    }
                    _log_event(event)
                    degraded.append(updated)
            except Exception as e:
                print(f"[drift_detector] WARNING: revenue drift check failed for one archetype: {e}")

        return degraded
    except Exception as e:
        print(f"[drift_detector] WARNING: detect_revenue_drift failed: {e}")
        return []


def detect_category_shift(
    category:           str,
    current_centroid:   np.ndarray,
    historical_centroid: np.ndarray,
    threshold:          float = _CATEGORY_SHIFT_DEFAULT,
) -> dict | None:
    """
    Detect if the visual style of a category has shifted significantly.

    Uses cosine distance: distance = 1 - cosine_similarity.

    Returns:
        drift event dict if shift detected (distance > threshold), None otherwise.
    Never raises.
    """
    try:
        if current_centroid is None or historical_centroid is None:
            return None
        if current_centroid.size == 0 or historical_centroid.size == 0:
            return None

        # L2-normalize both
        def _norm(v: np.ndarray) -> np.ndarray:
            n = np.linalg.norm(v)
            return v / (n + 1e-8)

        c_norm = _norm(current_centroid.astype(np.float32))
        h_norm = _norm(historical_centroid.astype(np.float32))

        cosine_sim = float(np.dot(c_norm, h_norm))
        cosine_dist = 1.0 - cosine_sim

        if cosine_dist > threshold:
            event = {
                "type":            "category_visual_shift",
                "category":        category,
                "cosine_distance": round(cosine_dist, 6),
                "cosine_similarity": round(cosine_sim, 6),
                "threshold":       threshold,
                "detected_at":     datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            _log_event(event)
            return event

        return None
    except Exception as e:
        print(f"[drift_detector] WARNING: detect_category_shift failed: {e}")
        return None


def run_drift_check(category: str) -> dict:
    """
    Run all 3 drift checks for a category.

    Loads data from archetype_memory and vector_store.
    Returns summary dict with results of all checks.
    Never raises.
    """
    try:
        from core.visual_intelligence import archetype_memory

        archetypes = archetype_memory.get_archetypes(category)

        results = {
            "category":       category,
            "run_at":         datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "flow_quality":   None,
            "revenue_drift":  [],
            "category_shift": None,
            "total_checks":   3,
            "drifts_detected": 0,
        }

        # Check 1: Flow quality drift — need similarity data from archetypes
        try:
            all_sims = [float(a.get("avg_similarity", 0.0)) for a in archetypes if a.get("avg_similarity")]
            if len(all_sims) >= 2:
                midpoint = max(len(all_sims) // 4, 1)
                recent_sims   = all_sims[-midpoint:]
                baseline_sims = all_sims
                drift1 = detect_flow_quality_drift(category, recent_sims, baseline_sims)
                results["flow_quality"] = drift1
                if drift1:
                    results["drifts_detected"] += 1
        except Exception as e:
            print(f"[drift_detector] WARNING: flow quality check failed: {e}")

        # Check 2: Revenue drift — no real metrics available from disk alone
        # Pass empty current_metrics → will only trigger if historical CTR exists
        try:
            degraded = detect_revenue_drift(category, archetypes, {})
            results["revenue_drift"] = degraded
            if degraded:
                results["drifts_detected"] += len(degraded)
        except Exception as e:
            print(f"[drift_detector] WARNING: revenue drift check failed: {e}")

        # Check 3: Category shift — compare first vs last archetype centroid
        try:
            centroids = []
            for a in archetypes:
                c = a.get("embedding_centroid")
                if c:
                    centroids.append(np.array(c, dtype=np.float32))

            if len(centroids) >= 2:
                drift3 = detect_category_shift(
                    category,
                    current_centroid=centroids[-1],
                    historical_centroid=centroids[0],
                )
                results["category_shift"] = drift3
                if drift3:
                    results["drifts_detected"] += 1
        except Exception as e:
            print(f"[drift_detector] WARNING: category shift check failed: {e}")

        return results

    except Exception as e:
        print(f"[drift_detector] WARNING: run_drift_check failed for '{category}': {e}")
        return {
            "category":        category,
            "run_at":          datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "error":           str(e),
            "drifts_detected": 0,
        }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _log_event(event: dict) -> None:
    """Append drift event to today's JSONL log file. Never raises."""
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        log_path = _LOG_DIR / f"{today}.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[drift_detector] WARNING: failed to log drift event: {e}")

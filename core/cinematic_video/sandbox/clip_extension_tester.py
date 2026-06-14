#!/usr/bin/env python3
"""
clip_extension_tester.py — Extend-mode boundary testing with drift tracking.

Tests how many times a clip can be extended before continuity breaks.
Simulates: generate base → extend 1x → extend 2x → extend 3x → …
Tracks drift accumulation per extension step.

Teaches the agent: "Extension is cheap but degrades — know when to stop."

SANDBOX-ONLY: Never touches production pipeline.
"""

from __future__ import annotations

import warnings

from core.cinematic_video.sandbox.schemas import (
    ExtensionTrial,
    _make_id,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Drift model — simulated degradation per extension
# ═══════════════════════════════════════════════════════════════════════════════

# Drift increases per extension (non-linear — accelerates after 3+)
_DRIFT_PER_EXTENSION: tuple[float, ...] = (0.0, 0.08, 0.18, 0.30, 0.45, 0.63, 0.82)

# Thresholds
_DRIFT_WARNING = 0.25    # Degraded
_DRIFT_FAILURE = 0.50    # Failed — stop extending
_DRIFT_ABORT    = 0.70   # Aborted — clip is useless

# Credit cost per extension
_EXTEND_COST = 0.8


def _estimate_drift(
    extension_index: int,
    shot_type: str = "",
) -> tuple[float, str, tuple[str, ...]]:
    """
    Estimate drift for a given extension index.

    Returns (drift_score, outcome, issues).
    """
    if extension_index >= len(_DRIFT_PER_EXTENSION):
        drift = _DRIFT_PER_EXTENSION[-1] + (extension_index - len(_DRIFT_PER_EXTENSION) + 1) * 0.15
    else:
        drift = _DRIFT_PER_EXTENSION[extension_index]

    # Apply shot-type risk modifier
    high_risk_shots = {"emotional_lifestyle_shot", "kinetic_montage_shot"}
    if shot_type in high_risk_shots:
        drift *= 1.3

    drift = min(drift, 1.0)

    issues: list[str] = []

    if extension_index == 0:
        return 0.0, "success", ()

    if drift > _DRIFT_ABORT:
        issues.append("Clip has become unusable — product unrecognizable")
        issues.append("Motion artifacts severe")
        return drift, "aborted", tuple(issues)

    if drift > _DRIFT_FAILURE:
        issues.append("Continuity broken — style significantly changed")
        issues.append("Lighting/palette drift visible")
        return drift, "failed", tuple(issues)

    if drift > _DRIFT_WARNING:
        issues.append("Minor drift detected — colors slightly shifting")
        return drift, "degraded", tuple(issues)

    return drift, "success", ()


def _recommendation(
    outcome: str,
    extension_index: int,
    drift_score: float,
) -> str:
    if outcome == "aborted":
        return "stop"
    if outcome == "failed":
        if extension_index <= 2:
            return "retry_with_anchor"
        return "stop"
    if outcome == "degraded":
        return "continue" if extension_index <= 2 else "stop"
    return "continue"


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def run_extension_trial(
    variation_id: str,
    max_extensions: int = 4,
    shot_type: str = "",
    dry_run: bool = True,
) -> tuple[ExtensionTrial, ...]:
    """
    Run an extension trial: generate base + extend N times.

    Returns one ExtensionTrial per extension step (including base at index 0).
    Never raises — returns empty tuple on error.

    Args:
        variation_id: The prompt variation being tested
        max_extensions: How many times to extend (default 4)
        shot_type: Shot type for risk adjustment
        dry_run: True = simulate, False = real Flow (not yet implemented)
    """
    if not dry_run:
        # Real Flow extension testing requires browser automation —
        # not yet implemented in sandbox. Falling back to simulated results.
        warnings.warn(
            "run_extension_trial(dry_run=False) is not yet implemented — "
            "real Flow browser automation is unavailable. "
            "Returning simulated results instead.",
            stacklevel=2,
        )

    results: list[ExtensionTrial] = []

    for idx in range(max_extensions + 1):  # 0 = base, 1-4 = extensions
        drift, outcome, issues = _estimate_drift(idx, shot_type)
        rec = _recommendation(outcome, idx, drift)
        cost = 1.0 if idx == 0 else _EXTEND_COST

        trial = ExtensionTrial(
            trial_id=_make_id("ext"),
            variation_id=variation_id,
            extension_index=idx,
            outcome=outcome,
            drift_score=round(drift, 3),
            credit_cost=int(cost),
            issues=issues,
            recommendation=rec,
        )
        results.append(trial)

        # Stop early if aborted
        if outcome == "aborted":
            break

    return tuple(results)


def batch_extension_trial(
    variation_ids: tuple[str, ...],
    max_extensions: int = 4,
    dry_run: bool = True,
) -> dict[str, tuple[ExtensionTrial, ...]]:
    """
    Run extension trials for multiple variations.

    Returns dict: variation_id → tuple of ExtensionTrial.
    """
    output: dict[str, tuple[ExtensionTrial, ...]] = {}
    for vid in variation_ids:
        output[vid] = run_extension_trial(vid, max_extensions, dry_run=dry_run)
    return output


def get_extension_health(
    trials: tuple[ExtensionTrial, ...],
) -> dict:
    """
    Summarize extension trial health.

    Returns dict with: total_extensions, healthy_extensions, degraded, failed,
    aborted, max_safe_extensions.
    """
    total = len([t for t in trials if t.extension_index > 0])
    healthy = len([t for t in trials if t.extension_index > 0 and t.outcome == "success"])
    degraded = len([t for t in trials if t.outcome == "degraded"])
    failed = len([t for t in trials if t.outcome == "failed"])
    aborted = len([t for t in trials if t.outcome == "aborted"])

    # Find the index where things started going wrong
    max_safe = 0
    for t in trials:
        if t.extension_index > 0 and t.outcome in ("failed", "aborted"):
            break
        if t.outcome in ("success", "degraded"):
            max_safe = t.extension_index

    return {
        "total_extensions": total,
        "healthy": healthy,
        "degraded": degraded,
        "failed": failed,
        "aborted": aborted,
        "max_safe_extensions": max_safe,
        "health_pct": (healthy / max(total, 1)) * 100,
    }


__all__ = [
    "run_extension_trial",
    "batch_extension_trial",
    "get_extension_health",
]

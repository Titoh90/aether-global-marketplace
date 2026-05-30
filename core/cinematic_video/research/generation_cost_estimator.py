#!/usr/bin/env python3
"""
generation_cost_estimator.py — Flow credit optimization engine.

Estimates credit costs for proposed video generations. Helps avoid
wasting limited daily credits. Teaches the agent when to use image-first,
when to extend, when to reuse frames, and when to abort.

CRITICAL RULE: NO wasted generations.

RESEARCH-ONLY: No video generation. Pure knowledge.
"""

from __future__ import annotations

import math

from core.cinematic_video.research.schemas import CinematicCostEstimate, StoryboardPattern

# ═══════════════════════════════════════════════════════════════════════════════
# Cost Model Constants
# ═══════════════════════════════════════════════════════════════════════════════

# Base credit cost per generation mode
_MODE_BASE_COST: dict[str, float] = {
    "text_to_video":         1.0,
    "image_to_video":        1.0,
    "frame_continuation":    1.0,
    "ingredients_to_video":  1.2,
    "extend_mode":           0.8,
    "jump_to_mode":          0.7,
    "scene_builder":         1.5,
}

# Retake buffer: extra credits budgeted for failed/retry generations
_RETAKE_BUFFER_FACTOR = 0.3  # 30% extra for retakes

# Daily credit budget (conservative estimate — adjust per account tier)
_DEFAULT_DAILY_BUDGET = 8

# Risk thresholds
_LOW_RISK_THRESHOLD = 0.3
_MEDIUM_RISK_THRESHOLD = 0.6
_HIGH_RISK_THRESHOLD = 0.85


# ═══════════════════════════════════════════════════════════════════════════════
# Shot → Flow Mode Mapping (module-level, computed once)
# ═══════════════════════════════════════════════════════════════════════════════

_SHOT_MODE_MAP: dict[str, str] = {
    "hero_shot":               "image_to_video",
    "macro_detail_shot":       "image_to_video",
    "emotional_lifestyle_shot": "text_to_video",
    "floating_product_shot":    "text_to_video",
    "transformation_shot":      "image_to_video",
    "unboxing_shot":            "image_to_video",
    "cinematic_reveal":         "text_to_video",
    "comparison_shot":          "image_to_video",
    "luxury_product_shot":      "image_to_video",
    "premium_tech_shot":        "image_to_video",
    "beauty_close_up":          "image_to_video",
    "kinetic_montage_shot":     "text_to_video",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Cost Estimation Engine
# ═══════════════════════════════════════════════════════════════════════════════

def estimate_cost(
    storyboard: StoryboardPattern,
    daily_budget: int = _DEFAULT_DAILY_BUDGET,
) -> CinematicCostEstimate:
    """
    Estimate credit cost for a storyboard.

    Computes per-mode credit breakdown, total cost, risk level,
    and whether the generation is viable within daily budget.
    """
    mode_breakdown: dict[str, int] = {}
    total_credits = 0.0

    for shot in storyboard.shot_sequence:
        # Determine primary mode for this shot type
        # Shot types map to production modes
        mode = _infer_mode_for_shot(shot.shot_type)
        base_cost = _MODE_BASE_COST.get(mode, 1.0)
        mode_breakdown[mode] = mode_breakdown.get(mode, 0) + 1
        total_credits += base_cost

    # Add retake buffer
    total_with_buffer = total_credits * (1.0 + _RETAKE_BUFFER_FACTOR)
    estimated = math.ceil(total_with_buffer)

    # Risk assessment
    risk_level = _assess_risk(storyboard, estimated, daily_budget)
    is_viable = estimated <= daily_budget

    # Optimization tips
    tips = _generate_optimization_tips(storyboard, estimated, daily_budget)

    return CinematicCostEstimate(
        estimate_id=f"cost_{storyboard.pattern_id}",
        storyboard_name=storyboard.name,
        total_shots=storyboard.total_shots,
        estimated_credits=estimated,
        mode_breakdown=mode_breakdown,
        risk_level=risk_level,
        optimization_tips=tuple(tips),
        is_viable=is_viable,
    )


def _infer_mode_for_shot(shot_type: str) -> str:
    """Infer the best Flow mode for a given shot type."""
    return _SHOT_MODE_MAP.get(shot_type, "text_to_video")


def _assess_risk(
    storyboard: StoryboardPattern, estimated_credits: int, daily_budget: int
) -> str:
    """Assess risk level for this generation plan."""
    budget_ratio = estimated_credits / daily_budget

    if budget_ratio > _HIGH_RISK_THRESHOLD:
        return "prohibitive"
    if budget_ratio > _MEDIUM_RISK_THRESHOLD:
        return "high"
    if budget_ratio > _LOW_RISK_THRESHOLD:
        return "medium"
    if storyboard.risk_level == "high":
        return "medium"
    return "low"


def _generate_optimization_tips(
    storyboard: StoryboardPattern, estimated_credits: int, daily_budget: int
) -> list[str]:
    """Generate tips to reduce credit usage."""
    tips: list[str] = []

    if estimated_credits > daily_budget:
        tips.append(
            f"EXCEEDS BUDGET: {estimated_credits} credits needed, {daily_budget} available. "
            "Split across multiple days or reduce shot count."
        )

    if storyboard.total_shots > 4:
        tips.append(
            f"Consider reducing from {storyboard.total_shots} to 4 shots. "
            "Drop the least essential shot. Fewer shots = less drift."
        )

    if storyboard.total_shots >= 3:
        tips.append(
            "Use image_to_video for the FIRST shot as a style anchor, "
            "then text_to_video for subsequent shots to save image upload credits."
        )

    # Check for extend opportunities
    has_orbit_sequence = any(
        "orbit" in s.camera_motion for s in storyboard.shot_sequence
    )
    if has_orbit_sequence:
        tips.append(
            "Orbit shots can be extended (extend_mode) instead of generating "
            "separate orbit clips. One orbit + extend = cheaper than two orbits."
        )

    # Check for reusable frames
    tips.append(
        "Export the last frame of each clip. Reuse as reference for the next clip "
        "(image_to_video). This costs 0 extra credits and improves continuity."
    )

    return tips


# ═══════════════════════════════════════════════════════════════════════════════
# Decision Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def should_use_image_first(shot_type: str) -> bool:
    """Determine if image_to_video should be used instead of text_to_video."""
    image_first_shots = {
        "hero_shot", "macro_detail_shot", "luxury_product_shot",
        "premium_tech_shot", "beauty_close_up", "unboxing_shot",
    }
    return shot_type in image_first_shots


def should_extend_instead_of_new_clip(shot_type: str) -> bool:
    """Determine if extend_mode is better than a new generation."""
    extend_preferred = {
        "hero_shot", "floating_product_shot", "luxury_product_shot",
    }
    return shot_type in extend_preferred


def should_reuse_frame(shot_index: int) -> bool:
    """Determine if frame reuse is appropriate for this shot position."""
    return shot_index > 0  # Always reuse frame from previous shot


def should_abort_sequence(
    failed_shots: int, total_shots: int, credits_used: int, daily_budget: int
) -> bool:
    """
    Determine if a sequence should be aborted based on failures and budget.

    Returns True if continuing is too risky.
    """
    failure_rate = failed_shots / max(total_shots, 1)
    budget_used_ratio = credits_used / max(daily_budget, 1)

    # Abort if >50% shots failed
    if failure_rate > 0.5:
        return True

    # Abort if >70% budget consumed
    if budget_used_ratio > 0.7:
        return True

    return False


def is_storyboard_too_risky(
    storyboard: StoryboardPattern, daily_budget: int = _DEFAULT_DAILY_BUDGET
) -> bool:
    """Check if a storyboard is too risky to attempt."""
    est = estimate_cost(storyboard, daily_budget)
    return est.risk_level in ("high", "prohibitive") or not est.is_viable


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "estimate_cost",
    "should_use_image_first",
    "should_extend_instead_of_new_clip",
    "should_reuse_frame",
    "should_abort_sequence",
    "is_storyboard_too_risky",
    "_DEFAULT_DAILY_BUDGET",
]

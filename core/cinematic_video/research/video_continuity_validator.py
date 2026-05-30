#!/usr/bin/env python3
"""
video_continuity_validator.py — Visual continuity validation for video sequences.

Validates palette consistency, product consistency, lighting continuity,
camera continuity, object persistence, and drift between scenes.

Non-blocking: scores and warns, never rejects.
RESEARCH-ONLY: No video generation. Pure knowledge and validation logic.
"""

from __future__ import annotations

import datetime
import hashlib

from core.cinematic_video.research.schemas import (
    ContinuityValidation,
    CONTINUITY_DIMENSIONS,
    CinematicShot,
    StoryboardStep,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Continuity Scoring
# ═══════════════════════════════════════════════════════════════════════════════

def validate_storyboard_continuity(
    storyboard_id: str,
    shot_sequence: tuple[StoryboardStep, ...] | tuple[CinematicShot, ...],
) -> ContinuityValidation:
    """
    Validate continuity across a storyboard's shot sequence.

    Checks all 8 continuity dimensions. Returns a ContinuityValidation
    with per-dimension scores, warnings, and overall pass/fail.

    Non-blocking: always returns a result, never raises.
    """
    if not shot_sequence:
        return ContinuityValidation(
            validation_id=_make_id(storyboard_id),
            validated_at=_now_iso(),
            dimensions_checked=tuple(CONTINUITY_DIMENSIONS),
            scores={d: 1.0 for d in CONTINUITY_DIMENSIONS},
            overall_score=1.0,
            warnings=(),
            passed=True,
        )

    dimensions = list(CONTINUITY_DIMENSIONS)
    scores: dict[str, float] = {}
    warnings: list[str] = []

    # Run each dimension check
    for dim in dimensions:
        score, dim_warnings = _check_dimension(dim, shot_sequence)
        scores[dim] = score
        warnings.extend(dim_warnings)

    overall = sum(scores.values()) / len(scores) if scores else 1.0
    passed = overall >= 0.6  # 60% threshold

    return ContinuityValidation(
        validation_id=_make_id(storyboard_id),
        validated_at=_now_iso(),
        dimensions_checked=tuple(dimensions),
        scores=scores,
        overall_score=round(overall, 3),
        warnings=tuple(warnings),
        passed=passed,
    )


def _check_dimension(
    dimension: str,
    shots: tuple[StoryboardStep, ...] | tuple[CinematicShot, ...],
) -> tuple[float, list[str]]:
    """Score a single continuity dimension across shots."""
    checkers = {
        "palette_coherence":    _check_palette_coherence,
        "product_consistency":  _check_product_consistency,
        "lighting_continuity":  _check_lighting_continuity,
        "camera_continuity":    _check_camera_continuity,
        "object_persistence":   _check_object_persistence,
        "motion_smoothness":    _check_motion_smoothness,
        "style_coherence":      _check_style_coherence,
        "framing_consistency":  _check_framing_consistency,
    }

    checker = checkers.get(dimension)
    if checker is None:
        return 1.0, []
    return checker(shots)


# ── Dimension Checkers ────────────────────────────────────────────────────────

def _check_palette_coherence(
    shots: tuple[StoryboardStep, ...] | tuple[CinematicShot, ...],
) -> tuple[float, list[str]]:
    """Check lighting style consistency — proxy for palette."""
    if len(shots) < 2:
        return 1.0, []

    lightings = [_get_lighting(s) for s in shots]
    unique = len(set(lightings))
    if unique == 1:
        return 1.0, []
    if unique <= len(shots) // 2:
        return 0.7, ["Lighting style varies between shots — palette may be inconsistent"]
    return 0.3, ["Multiple different lighting styles detected — high palette drift risk"]


def _check_product_consistency(
    shots: tuple[StoryboardStep, ...] | tuple[CinematicShot, ...],
) -> tuple[float, list[str]]:
    """Check shot type consistency — proxy for product consistency."""
    if len(shots) < 2:
        return 1.0, []

    shot_types = [_get_shot_type(s) for s in shots]
    # Having different shot types is expected and desirable — score based on variety appropriateness
    unique = len(set(shot_types))
    if unique == 1 and len(shots) > 2:
        return 0.6, ["All shots are the same type — lack of visual variety may indicate product isn't being shown differently"]
    return 0.85, []


def _check_lighting_continuity(
    shots: tuple[StoryboardStep, ...] | tuple[CinematicShot, ...],
) -> tuple[float, list[str]]:
    """Check that lighting changes are intentional."""
    if len(shots) < 2:
        return 1.0, []

    lightings = [_get_lighting(s) for s in shots]
    # Count transitions
    changes = sum(1 for i in range(1, len(lightings)) if lightings[i] != lightings[i-1])
    change_ratio = changes / (len(lightings) - 1)

    if change_ratio == 0:
        return 1.0, []
    if change_ratio <= 0.3:
        return 0.8, []
    if change_ratio <= 0.5:
        return 0.6, ["Frequent lighting changes may disrupt visual continuity"]
    return 0.3, ["Lighting changes with almost every shot — severe continuity risk"]


def _check_camera_continuity(
    shots: tuple[StoryboardStep, ...] | tuple[CinematicShot, ...],
) -> tuple[float, list[str]]:
    """Check camera motion consistency."""
    if len(shots) < 2:
        return 1.0, []

    motions = [_get_camera_motion(s) for s in shots]
    pacing = [_get_pacing(s) for s in shots]

    warnings: list[str] = []

    # Check pacing consistency
    unique_pacing = len(set(pacing))
    pacing_score = 1.0
    if unique_pacing > 2:
        pacing_score = 0.5
        warnings.append("Multiple pacing styles — inconsistent rhythm between shots")

    # Check for orbit direction (can't actually check direction, but flag multiple orbits as good)
    orbit_count = sum(1 for m in motions if "orbit" in m.lower())
    if orbit_count > 1 and orbit_count == len(motions):
        return 0.9, warnings  # Consistent orbits — good!

    return pacing_score, warnings


def _check_object_persistence(
    shots: tuple[StoryboardStep, ...] | tuple[CinematicShot, ...],
) -> tuple[float, list[str]]:
    """Check that product is referenced across all shots."""
    # All shots in a storyboard should reference the same product
    # We can't check the actual prompt content here, but we can verify
    # the storyboard structure is coherent
    if len(shots) < 2:
        return 1.0, []

    # Check for gaps — shots that don't seem product-focused
    non_product_shots = {"emotional_lifestyle_shot"}
    gap_count = sum(1 for s in shots if _get_shot_type(s) in non_product_shots)

    if gap_count > len(shots) // 2:
        return 0.4, ["More than half the shots are lifestyle/context — product may get lost"]

    return 0.85, []


def _check_motion_smoothness(
    shots: tuple[StoryboardStep, ...] | tuple[CinematicShot, ...],
) -> tuple[float, list[str]]:
    """Check for abrupt motion changes between shots."""
    if len(shots) < 2:
        return 1.0, []

    motions = [_get_camera_motion(s) for s in shots]

    # Check for incompatible motion transitions
    incompatible_pairs = {
        ("orbit", "handheld"),
        ("macro_close_up", "tracking_shot"),
        ("slow_reveal", "push_in"),
        ("crane_up", "whip_pan"),
    }

    warnings: list[str] = []
    issues = 0
    for i in range(len(motions) - 1):
        pair = (motions[i], motions[i+1])
        if pair in incompatible_pairs or tuple(reversed(pair)) in incompatible_pairs:
            issues += 1

    if issues == 0:
        return 1.0, []
    if issues == 1:
        return 0.7, ["One potentially jarring motion transition detected"]
    return 0.4, [f"{issues} incompatible motion transitions — motion discontinuity likely"]


def _check_style_coherence(
    shots: tuple[StoryboardStep, ...] | tuple[CinematicShot, ...],
) -> tuple[float, list[str]]:
    """Check overall style coherence across shots."""
    if len(shots) < 2:
        return 1.0, []

    # Collect aesthetic categories from shots if available
    aesthetics = []
    for s in shots:
        if hasattr(s, 'aesthetic_category'):
            aesthetics.append(s.aesthetic_category)

    if not aesthetics:
        return 0.5, ["Cannot verify style coherence — missing aesthetic metadata (neutral score)"]

    unique = len(set(aesthetics))
    if unique == 1:
        return 1.0, []
    if unique == 2:
        return 0.7, ["Two different aesthetic categories — minor style drift possible"]
    return 0.3, [f"{unique} different aesthetic categories — severe style incoherence risk"]


def _check_framing_consistency(
    shots: tuple[StoryboardStep, ...] | tuple[CinematicShot, ...],
) -> tuple[float, list[str]]:
    """Check framing/composition consistency."""
    if len(shots) < 2:
        return 1.0, []

    # Framing consistency is hard to validate without actual video
    # Score based on shot type variety — too much variety may indicate framing issues
    shot_types = [_get_shot_type(s) for s in shots]
    unique = len(set(shot_types))

    if unique <= 2:
        return 0.9, []  # Good — consistent shot types
    if unique <= 3:
        return 0.7, []  # Moderate variety
    return 0.5, ["High shot type diversity — framing may be inconsistent across shots"]


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _get_lighting(shot: StoryboardStep | CinematicShot) -> str:
    """Extract lighting from a shot."""
    if isinstance(shot, StoryboardStep):
        return shot.lighting
    if hasattr(shot, 'lighting_setup') and shot.lighting_setup:
        return shot.lighting_setup[0]
    return "unknown"


def _get_shot_type(shot: StoryboardStep | CinematicShot) -> str:
    """Extract shot type identifier."""
    if isinstance(shot, StoryboardStep):
        return shot.shot_type
    if hasattr(shot, 'shot_id'):
        return shot.shot_id
    return "unknown"


def _get_camera_motion(shot: StoryboardStep | CinematicShot) -> str:
    """Extract camera motion from a shot."""
    if isinstance(shot, StoryboardStep):
        return shot.camera_motion
    if hasattr(shot, 'camera_style'):
        return shot.camera_style
    return "unknown"


def _get_pacing(shot: StoryboardStep | CinematicShot) -> str:
    """Extract pacing from a shot."""
    if isinstance(shot, StoryboardStep):
        return shot.pacing
    if hasattr(shot, 'pacing'):
        return shot.pacing
    return "unknown"


def _make_id(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()[:12]


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "validate_storyboard_continuity",
]

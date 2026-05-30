#!/usr/bin/env python3
"""
generation_reviewer.py — Quality review of generated outputs.

Reviews simulated (and eventually real) Flow generation outputs.
Compares expected vs actual, flags quality issues, assigns severity.

Teaches the agent: "Not all generations are usable. Review before using."

SANDBOX-ONLY: Never touches production pipeline.
"""

from __future__ import annotations

from core.cinematic_video.sandbox.schemas import (
    GenerationReview,
    _make_id,
    _now_iso,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Quality assessment logic
# ═══════════════════════════════════════════════════════════════════════════════

def _score_drift(drift_score: float, extension_count: int) -> float:
    """Convert drift score to a 0.0–1.0 quality sub-score."""
    penalty = drift_score * (1.0 + extension_count * 0.2)
    return round(max(0.0, 1.0 - penalty), 3)


def _score_fidelity(shot_type: str, product_in_prompt: bool) -> float:
    """Estimate product fidelity based on shot type."""
    high_fidelity_shots = {
        "hero_shot", "macro_detail_shot", "luxury_product_shot",
        "premium_tech_shot", "beauty_close_up", "unboxing_shot",
    }
    if shot_type in high_fidelity_shots:
        base = 0.85
    else:
        base = 0.60

    if not product_in_prompt:
        base -= 0.20

    return round(max(0.0, base), 3)


def _score_aesthetic(lighting: str, atmosphere: str, lens_style: str) -> float:
    """Estimate aesthetic quality based on cinematic choices."""
    score = 0.70  # baseline

    # Lighting quality
    premium_lighting = {"dark_matte", "soft_rim", "golden_hour", "studio_three_point"}
    if lighting in premium_lighting:
        score += 0.10

    # Atmosphere quality
    premium_atmosphere = {"premium_commercial", "cinematic_drama", "luxury_dark"}
    if atmosphere in premium_atmosphere:
        score += 0.05

    # Lens quality
    premium_lens = {"macro", "anamorphic", "telephoto"}
    if lens_style in premium_lens:
        score += 0.05

    return round(min(1.0, score), 3)


def _determine_severity(
    overall: float,
    issues: tuple[str, ...],
) -> str:
    if overall < 0.3:
        return "critical"
    if overall < 0.5:
        return "error"
    if overall < 0.7 or len(issues) > 0:
        return "warning"
    return "info"


def _determine_recommendation(
    overall: float,
    drift_score: float,
    fidelity_score: float,
) -> str:
    if overall < 0.3:
        return "discard"
    if fidelity_score < 0.4:
        return "retake"
    if drift_score > 0.5:
        return "discard"
    if overall < 0.6:
        return "retake"
    return "approve"


def _collect_issues(
    drift_score: float,
    fidelity_score: float,
    aesthetic_score: float,
    shot_type: str,
    extension_count: int,
) -> tuple[str, ...]:
    issues: list[str] = []

    if drift_score > 0.5:
        issues.append(f"High drift ({drift_score:.2f}) — style significantly changed")
    elif drift_score > 0.25:
        issues.append(f"Moderate drift ({drift_score:.2f}) — review before using")

    if fidelity_score < 0.5:
        issues.append(f"Low product fidelity ({fidelity_score:.2f}) — product may not be recognizable")
    elif fidelity_score < 0.7:
        issues.append(f"Mediocre fidelity ({fidelity_score:.2f}) — product details may be inaccurate")

    if aesthetic_score < 0.6:
        issues.append(f"Low aesthetic quality ({aesthetic_score:.2f}) — consider different lighting/atmosphere")

    if extension_count > 3:
        issues.append(f"Many extensions ({extension_count}) — consider regenerating")

    return tuple(issues)


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def review_generation(
    variation_id: str,
    drift_score: float = 0.0,
    shot_type: str = "",
    lighting: str = "",
    atmosphere: str = "",
    lens_style: str = "",
    extension_count: int = 0,
    product_in_prompt: bool = True,
) -> GenerationReview:
    """
    Review one generated output for quality.

    Returns a GenerationReview with sub-scores, issues, severity, and recommendation.
    Never raises.
    """
    fidelity = _score_fidelity(shot_type, product_in_prompt)
    aesthetic = _score_aesthetic(lighting, atmosphere, lens_style)
    drift_quality = _score_drift(drift_score, extension_count)
    issues = _collect_issues(drift_score, fidelity, aesthetic, shot_type, extension_count)

    # Overall: weighted average
    overall = round(
        (fidelity * 0.35) + (aesthetic * 0.25) + (drift_quality * 0.40),
        3,
    )

    severity = _determine_severity(overall, issues)
    recommendation = _determine_recommendation(overall, drift_score, fidelity)

    return GenerationReview(
        review_id=_make_id("rev"),
        variation_id=variation_id,
        overall_score=overall,
        drift_score=drift_score,
        fidelity_score=fidelity,
        aesthetic_score=aesthetic,
        issues=issues,
        severity=severity,
        recommendation=recommendation,
    )


def batch_review(
    variations: tuple[dict, ...],
) -> tuple[GenerationReview, ...]:
    """
    Review multiple variations at once.

    Each dict in variations should have keys:
    variation_id, drift_score, shot_type, lighting, atmosphere, lens_style,
    extension_count, product_in_prompt (optional).
    """
    reviews: list[GenerationReview] = []
    for v in variations:
        review = review_generation(
            variation_id=v.get("variation_id", ""),
            drift_score=v.get("drift_score", 0.0),
            shot_type=v.get("shot_type", ""),
            lighting=v.get("lighting", ""),
            atmosphere=v.get("atmosphere", ""),
            lens_style=v.get("lens_style", ""),
            extension_count=v.get("extension_count", 0),
            product_in_prompt=v.get("product_in_prompt", True),
        )
        reviews.append(review)
    return tuple(reviews)


def get_review_summary(
    reviews: tuple[GenerationReview, ...],
) -> dict:
    """
    Summarize a batch of reviews.

    Returns dict with: total, approved, retakes, discards, avg_score, best_variation.
    """
    if not reviews:
        return {"total": 0, "approved": 0, "retakes": 0, "discards": 0,
                "avg_score": 0.0, "best_variation": ""}

    approved = sum(1 for r in reviews if r.recommendation == "approve")
    retakes = sum(1 for r in reviews if r.recommendation == "retake")
    discards = sum(1 for r in reviews if r.recommendation == "discard")
    avg = sum(r.overall_score for r in reviews) / len(reviews)

    best = max(reviews, key=lambda r: r.overall_score)

    return {
        "total": len(reviews),
        "approved": approved,
        "retakes": retakes,
        "discards": discards,
        "avg_score": round(avg, 3),
        "best_variation": best.variation_id,
        "best_score": best.overall_score,
    }


__all__ = [
    "review_generation",
    "batch_review",
    "get_review_summary",
]

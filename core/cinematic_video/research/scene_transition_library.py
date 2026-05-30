#!/usr/bin/env python3
"""
scene_transition_library.py — Complete scene transition catalog.

10 transition types for connecting cinematic video clips.
Each transition documented with compatibility, emotional impact, and drift risk.

RESEARCH-ONLY: No video generation. Pure knowledge.
"""

from __future__ import annotations

from core.cinematic_video.research.schemas import SceneTransition


_TRANSITIONS: tuple[SceneTransition, ...] = (
    SceneTransition(
        transition_id="match_cut",
        name="Match Cut",
        description=(
            "Cut between two shots where a visual element (shape, color, motion) "
            "matches, creating a seamless connection. The most cinematic transition."
        ),
        best_for=("hero_shot → macro_detail", "similar compositions across products"),
        emotional_impact="Seamless, sophisticated, professional",
        complexity="moderate",
        drift_risk=0.1,
        compatible_shots=("hero_shot", "macro_detail_shot", "luxury_product_shot", "premium_tech_shot"),
    ),
    SceneTransition(
        transition_id="dissolve",
        name="Dissolve",
        description=(
            "One shot gradually fades into the next. Soft, dreamy, elegant. "
            "The default transition for luxury and beauty content."
        ),
        best_for=("slow paced sequences", "luxury products", "beauty shots", "emotional transitions"),
        emotional_impact="Soft, elegant, dreamy, luxurious",
        complexity="simple",
        drift_risk=0.05,
        compatible_shots=("hero_shot", "macro_detail_shot", "emotional_lifestyle_shot",
                           "floating_product_shot", "luxury_product_shot", "beauty_close_up",
                           "cinematic_reveal"),
    ),
    SceneTransition(
        transition_id="hard_cut",
        name="Hard Cut",
        description=(
            "Abrupt cut from one shot to the next. Energetic, modern, direct. "
            "Best for fast-paced content and kinetic montages."
        ),
        best_for=("kinetic montages", "fast-paced ads", "social media content", "energetic sequences"),
        emotional_impact="Energetic, direct, modern, bold",
        complexity="simple",
        drift_risk=0.0,
        compatible_shots=("kinetic_montage_shot", "comparison_shot", "emotional_lifestyle_shot",
                           "unboxing_shot", "premium_tech_shot"),
    ),
    SceneTransition(
        transition_id="whip_pan",
        name="Whip Pan",
        description=(
            "Camera whips quickly from one shot to the next, creating motion blur "
            "that masks the cut. High energy, very dynamic."
        ),
        best_for=("kinetic sequences", "transition between different products", "energy products"),
        emotional_impact="Dynamic, energetic, exciting, fast-paced",
        complexity="moderate",
        drift_risk=0.3,
        compatible_shots=("kinetic_montage_shot", "comparison_shot", "premium_tech_shot"),
    ),
    SceneTransition(
        transition_id="light_flash",
        name="Light Flash",
        description=(
            "Brief flash of light (white or colored) between shots. Clean, "
            "premium,常用于 luxury and tech product transitions."
        ),
        best_for=("premium product reveals", "tech products", "clean transitions", "luxury sequences"),
        emotional_impact="Clean, premium, polished, professional",
        complexity="simple",
        drift_risk=0.05,
        compatible_shots=("hero_shot", "premium_tech_shot", "luxury_product_shot",
                           "cinematic_reveal", "beauty_close_up"),
    ),
    SceneTransition(
        transition_id="motion_blur",
        name="Motion Blur",
        description=(
            "Natural motion blur from camera movement masks the cut between shots. "
            "Feels organic and cinematic."
        ),
        best_for=("continuous camera sequences", "orbit-to-orbit transitions", "dynamic product shots"),
        emotional_impact="Organic, fluid, cinematic, natural",
        complexity="moderate",
        drift_risk=0.2,
        compatible_shots=("floating_product_shot", "premium_tech_shot", "kinetic_montage_shot"),
    ),
    SceneTransition(
        transition_id="product_morph",
        name="Product Morph",
        description=(
            "One product visually transforms/morphs into another. Ideal for "
            "color variants, model comparisons, or before/after."
        ),
        best_for=("color variants", "model upgrades", "before/after demonstrations", "product lines"),
        emotional_impact="Magical, innovative, satisfying, impressive",
        complexity="complex",
        drift_risk=0.5,
        compatible_shots=("transformation_shot", "comparison_shot", "hero_shot"),
    ),
    SceneTransition(
        transition_id="zoom_transition",
        name="Zoom Transition",
        description=(
            "Camera zooms into/through one shot to reveal the next. Creates "
            "momentum and a sense of movement through space."
        ),
        best_for=("product → detail transitions", "macro explorations", "depth reveals"),
        emotional_impact="Immersive, exploratory, dynamic",
        complexity="moderate",
        drift_risk=0.3,
        compatible_shots=("macro_detail_shot", "kinetic_montage_shot", "hero_shot"),
    ),
    SceneTransition(
        transition_id="mask_reveal",
        name="Mask Reveal",
        description=(
            "Next shot is revealed through a shape, object, or lighting mask. "
            "Creative and visually sophisticated."
        ),
        best_for=("creative brand content", "premium reveals", "artistic sequences"),
        emotional_impact="Creative, artistic, sophisticated, premium",
        complexity="complex",
        drift_risk=0.4,
        compatible_shots=("cinematic_reveal", "macro_detail_shot", "luxury_product_shot", "beauty_close_up"),
    ),
    SceneTransition(
        transition_id="continuous_motion",
        name="Continuous Motion",
        description=(
            "Camera motion continues unbroken across the cut — orbit continues, "
            "pan continues, etc. The smoothest possible transition."
        ),
        best_for=("orbit sequences", "360° product views", "continuous camera movements"),
        emotional_impact="Seamless, hypnotic, premium, immersive",
        complexity="complex",
        drift_risk=0.6,
        compatible_shots=("hero_shot", "floating_product_shot", "luxury_product_shot", "premium_tech_shot"),
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_transitions() -> tuple[SceneTransition, ...]:
    """Return all documented transitions."""
    return _TRANSITIONS


def get_transition(transition_id: str) -> SceneTransition | None:
    """Look up a transition by ID."""
    for t in _TRANSITIONS:
        if t.transition_id == transition_id:
            return t
    return None


def get_transitions_by_complexity(complexity: str) -> tuple[SceneTransition, ...]:
    """Filter by complexity: simple, moderate, complex."""
    return tuple(t for t in _TRANSITIONS if t.complexity == complexity)


def get_low_drift_transitions(max_drift: float = 0.2) -> tuple[SceneTransition, ...]:
    """Transitions with drift risk at or below threshold."""
    return tuple(t for t in _TRANSITIONS if t.drift_risk <= max_drift)


def get_transitions_for_shot(shot_id: str) -> tuple[SceneTransition, ...]:
    """Transitions compatible with a specific shot type."""
    return tuple(t for t in _TRANSITIONS if shot_id in t.compatible_shots)


def transition_count() -> int:
    return len(_TRANSITIONS)

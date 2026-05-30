#!/usr/bin/env python3
"""
prompt_cinema_patterns.py — Reusable cinematic prompt structure templates.

Documents the canonical prompt structure for cinematic ad generation:
PRODUCT + CAMERA + LIGHTING + MOTION + ENVIRONMENT + LENS + PACING + ATMOSPHERE

RESEARCH-ONLY: No video generation. Pure knowledge.
"""

from __future__ import annotations

from core.cinematic_video.research.schemas import PromptCinematicPattern


_PATTERNS: tuple[PromptCinematicPattern, ...] = (
    PromptCinematicPattern(
        pattern_id="standard_cinematic_commercial",
        name="Standard Cinematic Commercial",
        description=(
            "The canonical 8-component prompt structure for cinematic product ads. "
            "Ordered for optimal Flow prompt weighting: product first, style early, "
            "details last."
        ),
        structure_order=(
            "product_description",
            "camera_motion",
            "lighting",
            "environment_surface",
            "lens_style",
            "pacing",
            "atmosphere",
            "quality_anchors",
        ),
        template=(
            "{product}, "
            "{camera_motion}, "
            "{lighting}, "
            "{environment}, "
            "{lens}, "
            "{pacing}, "
            "{atmosphere}, "
            "{quality_anchors}"
        ),
        example_filled=(
            "matte black electric trimmer, "
            "slow orbit, "
            "dark luxury lighting, "
            "floating above reflective obsidian surface, "
            "macro lens, "
            "slow dramatic pacing, "
            "premium commercial aesthetic, "
            "ultra realistic, high-end product advertisement"
        ),
        applicable_shots=("hero_shot", "luxury_product_shot", "floating_product_shot", "premium_tech_shot"),
        strength=0.95,
    ),
    PromptCinematicPattern(
        pattern_id="lifestyle_human_centered",
        name="Lifestyle Human-Centered",
        description=(
            "Prompt structure for lifestyle shots with human subjects. "
            "Emphasizes environment, natural lighting, and authentic moments "
            "over technical perfection."
        ),
        structure_order=(
            "human_context",
            "product_usage",
            "environment",
            "lighting",
            "camera_motion",
            "mood",
            "quality_anchors",
        ),
        template=(
            "{human_context} using {product} in {environment}, "
            "{lighting}, "
            "{camera_motion}, "
            "{mood} moment, "
            "shallow depth of field, "
            "{quality_anchors}"
        ),
        example_filled=(
            "young professional using premium coffee maker in sunlit modern kitchen, "
            "warm natural window light, "
            "gentle handheld camera, "
            "authentic morning routine moment, "
            "shallow depth of field, "
            "aspirational lifestyle, warm cinematic tones"
        ),
        applicable_shots=("emotional_lifestyle_shot",),
        strength=0.85,
    ),
    PromptCinematicPattern(
        pattern_id="macro_detail_precision",
        name="Macro Detail Precision",
        description=(
            "Prompt structure for extreme close-up detail shots. "
            "Focuses on texture, material, and craftsmanship. "
            "Minimal environment, maximum detail."
        ),
        structure_order=(
            "product_detail",
            "macro_indicator",
            "lighting",
            "camera_motion",
            "focus_quality",
            "atmosphere",
            "quality_anchors",
        ),
        template=(
            "extreme macro close-up of {product_detail}, "
            "macro lens, "
            "{lighting}, "
            "{camera_motion}, "
            "shallow depth of field, "
            "{atmosphere}, "
            "{quality_anchors}"
        ),
        example_filled=(
            "extreme macro close-up of brushed metal watch dial texture, "
            "macro lens, "
            "soft rim light catching polished surfaces, "
            "very slow push-in, "
            "ultra shallow depth of field, "
            "premium craftsmanship aesthetic, "
            "ultra detailed, luxury product photography"
        ),
        applicable_shots=("macro_detail_shot", "beauty_close_up"),
        strength=0.90,
    ),
    PromptCinematicPattern(
        pattern_id="floating_product_minimal",
        name="Floating Product Minimal",
        description=(
            "Prompt structure for products suspended in dark void. "
            "Pure product focus, no environment, minimal composition. "
            "Apple-style product aesthetic."
        ),
        structure_order=(
            "product",
            "spatial_context",
            "camera_motion",
            "lighting",
            "composition",
            "atmosphere",
            "quality_anchors",
        ),
        template=(
            "{product} floating in dark space, "
            "{camera_motion}, "
            "{lighting}, "
            "no background, minimal composition, "
            "{atmosphere}, "
            "{quality_anchors}"
        ),
        example_filled=(
            "wireless earbuds floating in dark void, "
            "slow graceful orbit, "
            "soft rim light with subtle neon accent, "
            "no background, minimal composition, "
            "futuristic premium tech aesthetic, "
            "ultra realistic, high-end product photography"
        ),
        applicable_shots=("floating_product_shot", "premium_tech_shot"),
        strength=0.92,
    ),
    PromptCinematicPattern(
        pattern_id="dramatic_reveal",
        name="Dramatic Reveal",
        description=(
            "Prompt structure for dramatic product reveals — emerging from "
            "darkness, through light, with maximum anticipation."
        ),
        structure_order=(
            "reveal_action",
            "product",
            "lighting_transition",
            "camera_motion",
            "anticipation",
            "atmosphere",
            "quality_anchors",
        ),
        template=(
            "dramatic cinematic reveal of {product} emerging from darkness, "
            "{lighting_transition}, "
            "{camera_motion}, "
            "building anticipation, "
            "{atmosphere}, "
            "{quality_anchors}"
        ),
        example_filled=(
            "dramatic cinematic reveal of premium leather wallet emerging from darkness, "
            "single spotlight gradually illuminating rich leather texture, "
            "slow crane up revealing craftsmanship, "
            "building anticipation, "
            "luxury cinematic drama, "
            "ultra realistic, premium launch aesthetic"
        ),
        applicable_shots=("cinematic_reveal", "luxury_product_shot"),
        strength=0.88,
    ),
    PromptCinematicPattern(
        pattern_id="kinetic_montage",
        name="Kinetic Montage",
        description=(
            "Prompt structure for fast-paced, energetic montages. "
            "Multiple angles, dynamic camera, high energy. "
            "For social media ads that grab attention instantly."
        ),
        structure_order=(
            "product",
            "camera_style",
            "lighting",
            "energy",
            "multiple_angles",
            "atmosphere",
            "quality_anchors",
        ),
        template=(
            "kinetic product montage of {product}, "
            "{camera_style}, "
            "{lighting}, "
            "high energy dynamic movement, "
            "multiple angles and quick cuts, "
            "{atmosphere}, "
            "{quality_anchors}"
        ),
        example_filled=(
            "kinetic product montage of wireless gaming mouse, "
            "dynamic whip pans and push-ins, "
            "neon accent lighting on dark background, "
            "high energy dynamic movement, "
            "multiple angles and quick cuts, "
            "futuristic tech commercial, "
            "ultra realistic, high-end gaming product ad"
        ),
        applicable_shots=("kinetic_montage_shot",),
        strength=0.82,
    ),
    PromptCinematicPattern(
        pattern_id="beauty_glamour_soft",
        name="Beauty & Glamour Soft",
        description=(
            "Prompt structure for beauty and cosmetics products. "
            "Soft lighting, dewy textures, glamorous aesthetic. "
            "Emphasizes sensory appeal over technical specs."
        ),
        structure_order=(
            "product",
            "beauty_context",
            "lighting",
            "camera_motion",
            "texture_emphasis",
            "mood",
            "quality_anchors",
        ),
        template=(
            "beauty close-up of {product}, "
            "{beauty_context}, "
            "{lighting}, "
            "{camera_motion}, "
            "dewy luminous {texture_emphasis}, "
            "{mood}, "
            "{quality_anchors}"
        ),
        example_filled=(
            "beauty close-up of glass serum bottle with gold dropper, "
            "on white marble with fresh rose petals, "
            "soft diffused rim light with golden hour glow, "
            "very slow macro push-in, "
            "dewy luminous glass texture with light refractions, "
            "elegant luxury beauty mood, "
            "ultra realistic, premium beauty commercial"
        ),
        applicable_shots=("beauty_close_up", "luxury_product_shot"),
        strength=0.87,
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_patterns() -> tuple[PromptCinematicPattern, ...]:
    """Return all prompt patterns."""
    return _PATTERNS


def get_pattern(pattern_id: str) -> PromptCinematicPattern | None:
    """Look up a pattern by ID."""
    for p in _PATTERNS:
        if p.pattern_id == pattern_id:
            return p
    return None


def get_patterns_for_shot(shot_id: str) -> tuple[PromptCinematicPattern, ...]:
    """Get prompt patterns compatible with a specific shot type."""
    return tuple(
        p for p in _PATTERNS
        if shot_id in p.applicable_shots
    )


def get_strongest_pattern(shot_id: str) -> PromptCinematicPattern | None:
    """Get the highest-strength pattern for a given shot."""
    candidates = get_patterns_for_shot(shot_id)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.strength)


def pattern_count() -> int:
    return len(_PATTERNS)

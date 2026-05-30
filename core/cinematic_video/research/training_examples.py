#!/usr/bin/env python3
"""
training_examples.py — Anonymized pattern reference examples.

6 training examples of cinematic ad patterns. NO literal content copied.
Only structural patterns: pacing, cinematography, composition, rhythm.

RESEARCH-ONLY: No video generation. Pure knowledge.
"""

from __future__ import annotations

from core.cinematic_video.research.schemas import CinematicTrainingExample

_TRAINING_EXAMPLES: tuple[CinematicTrainingExample, ...] = (
    CinematicTrainingExample(
        example_id="luxury_tech_dark_floating",
        category="luxury_tech",
        shot_count=3,
        dominant_style="luxury_dark",
        camera_patterns=("floating_object_orbit", "macro_close_up", "dolly_in"),
        pacing_pattern="slow_dramatic",
        hook_structure="Dark void reveal — product materializes from darkness with rim light",
        composition_notes=(
            "Product centered in dark void — zero background distraction",
            "Slow orbit reveals product from all angles",
            "Macro detail of engineering/materials as second beat",
            "CTA frame with centered logo + clean product",
            "Rim light creates separation from dark background",
            "No human elements — pure product focus",
        ),
        source_type="pattern_synthesis",
    ),
    CinematicTrainingExample(
        example_id="cinematic_beauty_soft_glamour",
        category="cinematic_beauty",
        shot_count=4,
        dominant_style="luxury_dark",
        camera_patterns=("macro_close_up", "orbit", "slow_reveal", "rack_focus"),
        pacing_pattern="slow_dramatic",
        hook_structure="Dewy macro texture → full product reveal → ingredient detail → lifestyle glow",
        composition_notes=(
            "Extreme macro emphasizes texture and light refraction",
            "Dewy/luminous surfaces with soft rim lighting",
            "Golden hour warmth in lifestyle context shots",
            "Glass and gold accents catch and scatter light",
            "Rose petals or marble surfaces as elegant props",
            "Shallow depth of field keeps focus on product",
            "Soft focus background bokeh for premium feel",
        ),
        source_type="pattern_synthesis",
    ),
    CinematicTrainingExample(
        example_id="floating_amazon_product_minimal",
        category="floating_product",
        shot_count=3,
        dominant_style="tech_futuristic",
        camera_patterns=("floating_object_orbit", "push_in", "top_down_rotation"),
        pacing_pattern="medium_commercial",
        hook_structure="Product floating in void → feature callout → lifestyle context",
        composition_notes=(
            "Clean white or dark void — no environment",
            "Slow rotation reveals all angles efficiently",
            "Feature callouts via push-in on key areas",
            "Top-down flat lay for packaging/accessories",
            "Clean Amazon-style product photography aesthetic",
            "Maximum product clarity — no distracting elements",
        ),
        source_type="pattern_synthesis",
    ),
    CinematicTrainingExample(
        example_id="apple_style_premium_tech",
        category="premium_tech",
        shot_count=4,
        dominant_style="tech_futuristic",
        camera_patterns=("floating_object_orbit", "macro_close_up", "crane_up", "cinematic_pan"),
        pacing_pattern="medium_commercial",
        hook_structure="Floating product in dark space → engineering detail → dramatic reveal → lifestyle integration",
        composition_notes=(
            "Minimal dark background — Apple-style precision",
            "Floating product with subtle shadow/reflection",
            "Macro shots of materials: aluminum texture, glass edges",
            "Slow, deliberate camera movements",
            "Neon accent or soft rim light for depth",
            "CTA frame: product centered + simple text overlay space",
            "Transitions are clean dissolves or match cuts",
        ),
        source_type="pattern_synthesis",
    ),
    CinematicTrainingExample(
        example_id="warm_lifestyle_ecommerce",
        category="warm_lifestyle",
        shot_count=4,
        dominant_style="warm_lifestyle",
        camera_patterns=("handheld", "top_down_rotation", "dolly_out", "cinematic_pan"),
        pacing_pattern="medium_commercial",
        hook_structure="Human interaction → product detail → environment reveal → aspirational moment",
        composition_notes=(
            "Natural window light — warm and inviting",
            "Handheld camera for authentic, unscripted feel",
            "Product in use — not sterile product photography",
            "Golden hour or morning light as ambient",
            "Context-rich environments: kitchens, living spaces",
            "Human hands or partial human presence",
            "Shallow depth of field on emotional moments",
        ),
        source_type="pattern_synthesis",
    ),
    CinematicTrainingExample(
        example_id="kinetic_social_montage",
        category="kinetic_montage",
        shot_count=5,
        dominant_style="tech_futuristic",
        camera_patterns=("whip_pan", "push_in", "tracking_shot", "top_down_rotation", "zoom_transition"),
        pacing_pattern="fast_kinetic",
        hook_structure="Attention grab in 0.5s → rapid angle changes → product feature → CTA → loop",
        composition_notes=(
            "Rapid cuts between angles — 1-2s per shot",
            "Neon accent lighting on dark background",
            "Whip pans and motion blur transitions",
            "Product shown from multiple angles rapidly",
            "Energy sustained throughout — no slow moments",
            "Loop-friendly: end matches beginning for seamless replay",
            "Optimized for TikTok/Reels vertical format",
        ),
        source_type="pattern_synthesis",
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_examples() -> tuple[CinematicTrainingExample, ...]:
    """Return all training examples."""
    return _TRAINING_EXAMPLES


def get_example(example_id: str) -> CinematicTrainingExample | None:
    """Look up an example by ID."""
    for e in _TRAINING_EXAMPLES:
        if e.example_id == example_id:
            return e
    return None


def get_examples_by_category(category: str) -> tuple[CinematicTrainingExample, ...]:
    """Get examples for a specific category."""
    return tuple(e for e in _TRAINING_EXAMPLES if e.category == category)


def example_count() -> int:
    return len(_TRAINING_EXAMPLES)

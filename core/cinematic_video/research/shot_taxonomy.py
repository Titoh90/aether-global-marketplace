#!/usr/bin/env python3
"""
shot_taxonomy.py — Complete cinematic shot type taxonomy.

12 shot types cataloged with camera style, lens, lighting, pacing,
motion profile, aesthetic category, and prompt scaffolds.

RESEARCH-ONLY: No video generation. Pure knowledge.
"""

from __future__ import annotations

from core.cinematic_video.research.schemas import CinematicShot


_SHOTS: tuple[CinematicShot, ...] = (
    CinematicShot(
        shot_id="hero_shot",
        name="Hero Shot",
        description=(
            "The definitive product beauty shot. Centered, perfectly lit, "
            "slowly rotating or with subtle motion. The 'money shot' of "
            "product advertising. Used as opening or closing shot."
        ),
        category="hero_shot",
        camera_style="hero_shot",
        lens_style="standard_prime",
        lighting_setup=("dark_matte", "soft_rim", "product_spotlight"),
        pacing="slow_dramatic",
        motion_profile="Centered product, slow orbit or subtle float, minimal background movement",
        aesthetic_category="premium_commercial",
        compatible_transitions=("dissolve", "match_cut", "continuous_motion"),
        prompt_scaffold=(
            "hero shot of {product}, centered composition, {lighting}, "
            "cinematic commercial, ultra realistic, premium product photography, "
            "high-end advertisement, {camera_motion}"
        ),
    ),
    CinematicShot(
        shot_id="macro_detail_shot",
        name="Macro Detail Shot",
        description=(
            "Extreme close-up revealing texture, materials, and craftsmanship. "
            "Shows details invisible to the naked eye. Essential for luxury "
            "and premium products to communicate quality."
        ),
        category="macro_detail_shot",
        camera_style="macro_close_up",
        lens_style="macro",
        lighting_setup=("soft_rim", "product_spotlight"),
        pacing="slow_dramatic",
        motion_profile="Very slow push-in or gentle orbit, extreme shallow depth of field",
        aesthetic_category="luxury_dark",
        compatible_transitions=("dissolve", "match_cut", "mask_reveal"),
        prompt_scaffold=(
            "extreme macro close-up of {product_detail}, {lighting}, "
            "macro lens, ultra detailed, shallow depth of field, "
            "premium craftsmanship, cinematic commercial"
        ),
    ),
    CinematicShot(
        shot_id="emotional_lifestyle_shot",
        name="Emotional Lifestyle Shot",
        description=(
            "Product in human context — being used, enjoyed, or part of "
            "an aspirational lifestyle. Warm, relatable, emotional. "
            "Builds desire through identification, not specs."
        ),
        category="emotional_lifestyle_shot",
        camera_style="handheld",
        lens_style="standard_prime",
        lighting_setup=("golden_hour", "natural_window", "warm_lifestyle"),
        pacing="medium_commercial",
        motion_profile="Gentle handheld, human-scale movement, natural and unforced",
        aesthetic_category="warm_lifestyle",
        compatible_transitions=("dissolve", "hard_cut", "light_flash"),
        prompt_scaffold=(
            "lifestyle shot of person using {product} in {environment}, "
            "{lighting}, warm authentic moment, shallow depth of field, "
            "aspirational lifestyle, natural composition"
        ),
    ),
    CinematicShot(
        shot_id="floating_product_shot",
        name="Floating Product Shot",
        description=(
            "Product suspended in dark void or minimal space. Pure product "
            "focus with no environmental distraction. Very premium, "
            "tech-forward, futuristic look."
        ),
        category="floating_product_shot",
        camera_style="floating_object_orbit",
        lens_style="standard_prime",
        lighting_setup=("dark_matte", "soft_rim", "neon_accent"),
        pacing="slow_dramatic",
        motion_profile="Slow orbit around floating product, no background, minimal shadows",
        aesthetic_category="tech_futuristic",
        compatible_transitions=("dissolve", "motion_blur", "continuous_motion"),
        prompt_scaffold=(
            "{product} floating in dark space, slow orbit, {lighting}, "
            "no background, minimal composition, futuristic premium commercial, "
            "ultra realistic product photography"
        ),
    ),
    CinematicShot(
        shot_id="transformation_shot",
        name="Transformation Shot",
        description=(
            "Shows a product or result transformation — before/after, "
            "assembly, color change, or state transition. Powerful for "
            "demonstrating product efficacy."
        ),
        category="transformation_shot",
        camera_style="push_in",
        lens_style="standard_prime",
        lighting_setup=("studio_three_point", "high_key_commercial"),
        pacing="medium_commercial",
        motion_profile="Push in during transformation, or match cut between states",
        aesthetic_category="premium_commercial",
        compatible_transitions=("match_cut", "product_morph", "dissolve"),
        prompt_scaffold=(
            "transformation of {product} from {state_a} to {state_b}, "
            "{lighting}, cinematic commercial, smooth transition, "
            "dramatic reveal, premium product demonstration"
        ),
    ),
    CinematicShot(
        shot_id="unboxing_shot",
        name="Unboxing Shot",
        description=(
            "Product being revealed from packaging. Satisfying, anticipation-"
            "building. Popular on social media. Emphasizes premium packaging "
            "and first-impression experience."
        ),
        category="unboxing_shot",
        camera_style="top_down_rotation",
        lens_style="standard_prime",
        lighting_setup=("high_key_commercial", "studio_three_point", "natural_window"),
        pacing="medium_commercial",
        motion_profile="Top-down or eye-level, slow reveal from packaging, satisfying motions",
        aesthetic_category="minimal_elegance",
        compatible_transitions=("dissolve", "hard_cut", "mask_reveal"),
        prompt_scaffold=(
            "cinematic unboxing of {product}, {lighting}, "
            "satisfying reveal, premium packaging, clean composition, "
            "commercial product photography"
        ),
    ),
    CinematicShot(
        shot_id="cinematic_reveal",
        name="Cinematic Reveal",
        description=(
            "Dramatic product reveal — emerging from darkness, from behind "
            "an obstacle, or through lighting. Builds maximum anticipation. "
            "Best for flagship products and launches."
        ),
        category="cinematic_reveal",
        camera_style="slow_reveal",
        lens_style="cinematic_shallow_dof",
        lighting_setup=("low_key_dramatic", "dark_matte", "product_spotlight"),
        pacing="slow_dramatic",
        motion_profile="Very slow reveal, dramatic lighting transition, maximum anticipation",
        aesthetic_category="cinematic_drama",
        compatible_transitions=("dissolve", "light_flash", "mask_reveal"),
        prompt_scaffold=(
            "dramatic cinematic reveal of {product} emerging from darkness, "
            "{lighting}, slow reveal, maximum anticipation, "
            "cinematic commercial, premium launch aesthetic"
        ),
    ),
    CinematicShot(
        shot_id="comparison_shot",
        name="Comparison Shot",
        description=(
            "Side-by-side or sequential comparison of products, versions, "
            "or before/after. Clear visual communication of differences. "
            "Educational and convincing."
        ),
        category="comparison_shot",
        camera_style="cinematic_pan",
        lens_style="standard_prime",
        lighting_setup=("studio_three_point", "high_key_commercial"),
        pacing="medium_commercial",
        motion_profile="Pan between subjects, or split-screen composition, clear visual separation",
        aesthetic_category="minimal_elegance",
        compatible_transitions=("hard_cut", "whip_pan", "match_cut"),
        prompt_scaffold=(
            "product comparison shot, {product_a} and {product_b} side by side, "
            "{lighting}, clean composition, commercial photography, "
            "educational product demonstration"
        ),
    ),
    CinematicShot(
        shot_id="luxury_product_shot",
        name="Luxury Product Shot",
        description=(
            "Premium, dark, moody product photography. Emphasizes materials, "
            "craftsmanship, and exclusivity. For high-end products where "
            "aspiration is the primary selling point."
        ),
        category="luxury_product_shot",
        camera_style="orbit",
        lens_style="macro",
        lighting_setup=("dark_matte", "soft_rim", "reflective_surface", "product_spotlight"),
        pacing="slow_dramatic",
        motion_profile="Slow deliberate orbit, dark reflective surfaces, dramatic shallow depth of field",
        aesthetic_category="luxury_dark",
        compatible_transitions=("dissolve", "match_cut", "continuous_motion"),
        prompt_scaffold=(
            "luxury product shot of {product} on dark reflective obsidian surface, "
            "{lighting}, slow orbit, macro lens, premium craftsmanship, "
            "cinematic commercial, ultra realistic, high-end luxury advertisement"
        ),
    ),
    CinematicShot(
        shot_id="premium_tech_shot",
        name="Premium Tech Shot",
        description=(
            "Clean, precise, tech-forward product presentation. Emphasizes "
            "design, engineering, and innovation. Dark backgrounds with "
            "accent lighting. Apple-style product aesthetic."
        ),
        category="premium_tech_shot",
        camera_style="floating_object_orbit",
        lens_style="standard_prime",
        lighting_setup=("dark_matte", "soft_rim", "neon_accent", "product_spotlight"),
        pacing="medium_commercial",
        motion_profile="Clean floating orbit, precise movements, minimal environment, tech-forward",
        aesthetic_category="tech_futuristic",
        compatible_transitions=("hard_cut", "motion_blur", "continuous_motion"),
        prompt_scaffold=(
            "premium tech product shot of {product}, {lighting}, "
            "floating in dark space, clean minimal composition, "
            "ultra realistic, high-end tech commercial, precise industrial design"
        ),
    ),
    CinematicShot(
        shot_id="beauty_close_up",
        name="Beauty Close-Up",
        description=(
            "Soft, glamorous close-up for beauty and cosmetics products. "
            "Emphasizes texture, color, and sensory appeal. Dewy, luminous, "
            "glowing aesthetic."
        ),
        category="beauty_close_up",
        camera_style="macro_close_up",
        lens_style="macro",
        lighting_setup=("soft_rim", "golden_hour", "product_spotlight"),
        pacing="slow_dramatic",
        motion_profile="Very slow macro push-in, dewy highlights, glowing soft focus background",
        aesthetic_category="luxury_dark",
        compatible_transitions=("dissolve", "light_flash", "mask_reveal"),
        prompt_scaffold=(
            "beauty close-up of {product}, {lighting}, "
            "macro lens, dewy luminous texture, soft focus background, "
            "premium beauty commercial, glamorous product photography"
        ),
    ),
    CinematicShot(
        shot_id="kinetic_montage_shot",
        name="Kinetic Montage Shot",
        description=(
            "Fast-paced, energetic montage of product angles and details. "
            "High energy, quick cuts, dynamic movement. For social media "
            "ads that need to grab attention in first 2 seconds."
        ),
        category="kinetic_montage_shot",
        camera_style="tracking_shot",
        lens_style="wide_angle",
        lighting_setup=("neon_accent", "high_key_commercial", "product_spotlight"),
        pacing="fast_kinetic",
        motion_profile="Fast cuts, whip pans, dynamic angles, high energy, rapid shot changes",
        aesthetic_category="tech_futuristic",
        compatible_transitions=("whip_pan", "motion_blur", "hard_cut", "zoom_transition"),
        prompt_scaffold=(
            "kinetic product montage of {product}, {lighting}, "
            "dynamic camera movement, fast cuts, high energy, "
            "commercial advertising style, multiple angles"
        ),
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_shots() -> tuple[CinematicShot, ...]:
    """Return all 12 shot types."""
    return _SHOTS


def get_shot(shot_id: str) -> CinematicShot | None:
    """Look up a shot by ID."""
    for s in _SHOTS:
        if s.shot_id == shot_id:
            return s
    return None


def get_shots_by_aesthetic(aesthetic: str) -> tuple[CinematicShot, ...]:
    """Get shots matching an aesthetic category."""
    return tuple(s for s in _SHOTS if s.aesthetic_category == aesthetic)


def get_shots_by_pacing(pacing: str) -> tuple[CinematicShot, ...]:
    """Get shots with a specific pacing."""
    return tuple(s for s in _SHOTS if s.pacing == pacing)


def get_shots_by_category(category: str) -> tuple[CinematicShot, ...]:
    """Get shots of a specific category."""
    return tuple(s for s in _SHOTS if s.category == category)


def get_compatible_shots(transition_id: str) -> tuple[CinematicShot, ...]:
    """Get shots compatible with a specific transition."""
    return tuple(
        s for s in _SHOTS
        if transition_id in s.compatible_transitions
    )


def shot_count() -> int:
    return len(_SHOTS)

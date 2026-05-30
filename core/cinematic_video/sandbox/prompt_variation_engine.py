#!/usr/bin/env python3
"""
prompt_variation_engine.py — Systematic prompt variation generator.

Generates prompt variations from a base prompt using the cinematic
knowledge libraries. Each variation changes ONE dimension at a time
(shot type, camera motion, lighting, pacing, atmosphere, etc.).

Teaches the agent: "Not all prompts are equal — test systematically."

SANDBOX-ONLY: Never touches production pipeline.
"""

from __future__ import annotations

from core.cinematic_video.sandbox.schemas import (
    PromptVariation,
    _make_id,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Variation generators — one per dimension
# ═══════════════════════════════════════════════════════════════════════════════


def _vary_shot_type(base_prompt: str, product: str) -> list[PromptVariation]:
    """Generate variations by cycling through shot types."""
    try:
        from core.cinematic_video.research.shot_taxonomy import get_all_shots
        shots = get_all_shots()
    except ImportError:
        shots = ()
    variations: list[PromptVariation] = []
    for shot in shots[:4]:  # Cap at 4 per dimension
        vid = _make_id("var")
        # Append shot-specific framing to prompt
        varied = f"{base_prompt} | Shot: {shot.name} ({shot.camera_style}, {shot.description[:60]})"
        variations.append(PromptVariation(
            variation_id=vid,
            base_prompt=base_prompt,
            varied_prompt=varied,
            dimension="shot_type",
            change_description=f"Changed shot type to {shot.name}",
            shot_type=shot.shot_id,
            camera_motion=shot.camera_style,
            lens_style=shot.lens_style,
            pacing=shot.pacing,
            atmosphere=shot.aesthetic_category,
        ))
    return variations


def _vary_camera_motion(base_prompt: str, product: str) -> list[PromptVariation]:
    try:
        from core.cinematic_video.research.camera_motion_library import get_all_motions
        motions = get_all_motions()
    except ImportError:
        motions = ()
    variations: list[PromptVariation] = []
    for motion in motions[:4]:
        vid = _make_id("var")
        varied = f"{base_prompt} | Camera: {motion.name} ({motion.description[:50]})"
        variations.append(PromptVariation(
            variation_id=vid,
            base_prompt=base_prompt,
            varied_prompt=varied,
            dimension="camera_motion",
            change_description=f"Changed camera motion to {motion.name}",
            camera_motion=motion.motion_id,
        ))
    return variations


def _vary_lighting(base_prompt: str, product: str) -> list[PromptVariation]:
    lighting_options = (
        ("dark_matte", "Dark matte, premium shadows"),
        ("soft_rim", "Soft rim light, elegant glow"),
        ("high_key_commercial", "High-key commercial, bright and clean"),
        ("golden_hour", "Golden hour, warm natural light"),
        ("studio_three_point", "Studio three-point, professional"),
        ("neon_accent", "Neon accent, modern vibrant"),
    )
    variations: list[PromptVariation] = []
    for lid, ldesc in lighting_options[:4]:
        vid = _make_id("var")
        varied = f"{base_prompt} | Lighting: {ldesc}"
        variations.append(PromptVariation(
            variation_id=vid,
            base_prompt=base_prompt,
            varied_prompt=varied,
            dimension="lighting",
            change_description=f"Changed lighting to {ldesc}",
            lighting=lid,
        ))
    return variations


def _vary_pacing(base_prompt: str, product: str) -> list[PromptVariation]:
    pacing_options = (
        ("slow_dramatic", "Slow dramatic movement, weighty and deliberate"),
        ("medium_commercial", "Medium commercial pace, balanced"),
        ("fast_kinetic", "Fast kinetic energy, dynamic cuts"),
        ("variable_rhythm", "Variable rhythm, unpredictable pace"),
    )
    variations: list[PromptVariation] = []
    for pid, pdesc in pacing_options:
        vid = _make_id("var")
        varied = f"{base_prompt} | Pacing: {pdesc}"
        variations.append(PromptVariation(
            variation_id=vid,
            base_prompt=base_prompt,
            varied_prompt=varied,
            dimension="pacing",
            change_description=f"Changed pacing to {pdesc}",
            pacing=pid,
        ))
    return variations


def _vary_atmosphere(base_prompt: str, product: str) -> list[PromptVariation]:
    atmosphere_options = (
        ("premium_commercial", "Premium commercial atmosphere"),
        ("cinematic_drama", "Cinematic dramatic atmosphere"),
        ("minimal_elegance", "Minimal elegant atmosphere"),
        ("luxury_dark", "Luxury dark atmosphere"),
        ("tech_futuristic", "Tech futuristic atmosphere"),
    )
    variations: list[PromptVariation] = []
    for aid, adesc in atmosphere_options[:4]:
        vid = _make_id("var")
        varied = f"{base_prompt} | Atmosphere: {adesc}"
        variations.append(PromptVariation(
            variation_id=vid,
            base_prompt=base_prompt,
            varied_prompt=varied,
            dimension="atmosphere",
            change_description=f"Changed atmosphere to {adesc}",
            atmosphere=aid,
        ))
    return variations


def _vary_lens_style(base_prompt: str, product: str) -> list[PromptVariation]:
    lens_options = (
        ("macro", "Macro lens, extreme close-up detail"),
        ("wide_angle", "Wide angle, immersive scope"),
        ("telephoto", "Telephoto, compressed perspective"),
        ("anamorphic", "Anamorphic, cinematic widescreen feel"),
    )
    variations: list[PromptVariation] = []
    for lid, ldesc in lens_options:
        vid = _make_id("var")
        varied = f"{base_prompt} | Lens: {ldesc}"
        variations.append(PromptVariation(
            variation_id=vid,
            base_prompt=base_prompt,
            varied_prompt=varied,
            dimension="lens_style",
            change_description=f"Changed lens to {ldesc}",
            lens_style=lid,
        ))
    return variations


def _vary_aspect_ratio(base_prompt: str, product: str) -> list[PromptVariation]:
    ratios = ("9:16", "1:1", "4:5", "16:9")
    labels = ("9:16 vertical (Reels/TikTok)", "1:1 square (feed)", "4:5 portrait (feed)", "16:9 landscape (YouTube)")
    variations: list[PromptVariation] = []
    for ratio, label in zip(ratios, labels):
        vid = _make_id("var")
        varied = f"{base_prompt} | Aspect: {label}"
        variations.append(PromptVariation(
            variation_id=vid,
            base_prompt=base_prompt,
            varied_prompt=varied,
            dimension="aspect_ratio",
            change_description=f"Changed aspect ratio to {label}",
            aspect_ratio=ratio,
        ))
    return variations


# ═══════════════════════════════════════════════════════════════════════════════
# Dimension dispatcher
# ═══════════════════════════════════════════════════════════════════════════════

_VARIATION_FUNCTIONS: dict[str, callable] = {
    "shot_type":     _vary_shot_type,
    "camera_motion": _vary_camera_motion,
    "lighting":      _vary_lighting,
    "pacing":        _vary_pacing,
    "atmosphere":    _vary_atmosphere,
    "lens_style":    _vary_lens_style,
    "aspect_ratio":  _vary_aspect_ratio,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def generate_variations(
    base_prompt: str,
    product: str = "",
    dimensions: tuple[str, ...] = ("shot_type", "camera_motion", "lighting"),
    max_total: int = 12,
) -> tuple[PromptVariation, ...]:
    """
    Generate systematic prompt variations across chosen dimensions.

    Each dimension produces up to 4 variations. Total capped at max_total.
    NEVER raises — returns empty tuple on error.

    Args:
        base_prompt: The starting prompt to vary from
        product: Optional product name for shot-type selection
        dimensions: Which VARIATION_DIMENSIONS to vary (default: shot, camera, lighting)
        max_total: Maximum total variations to return

    Returns:
        Tuple of PromptVariation — sorted by dimension
    """
    all_variations: list[PromptVariation] = []

    for dim in dimensions:
        if dim not in _VARIATION_FUNCTIONS:
            continue
        fn = _VARIATION_FUNCTIONS[dim]
        try:
            dim_variations = fn(base_prompt, product)
            all_variations.extend(dim_variations)
        except Exception:
            # Never raise — skip this dimension
            continue

    # Cap at max_total
    return tuple(all_variations[:max_total])


def generate_single_variation(
    base_prompt: str,
    dimension: str,
    product: str = "",
    index: int = 0,
) -> PromptVariation | None:
    """
    Generate a single prompt variation for a specific dimension.

    Returns None if the dimension is invalid or generation fails.
    """
    if dimension not in _VARIATION_FUNCTIONS:
        return None
    try:
        variations = _VARIATION_FUNCTIONS[dimension](base_prompt, product)
        if index < len(variations):
            return variations[index]
        return variations[0] if variations else None
    except Exception:
        return None


def variation_count_for_dimensions(
    dimensions: tuple[str, ...],
) -> int:
    """Estimate how many variations would be generated for given dimensions."""
    count = 0
    for dim in dimensions:
        if dim in _VARIATION_FUNCTIONS:
            count += 4  # Each dimension produces ~4 variations
    return min(count, 12)


__all__ = [
    "generate_variations",
    "generate_single_variation",
    "variation_count_for_dimensions",
]

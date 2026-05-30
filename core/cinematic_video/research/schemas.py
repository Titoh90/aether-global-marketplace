#!/usr/bin/env python3
"""
schemas.py — Frozen dataclasses for Cinematic Video Research Layer.

READ-ONLY RESEARCH LAYER: No video generation. No pipeline modification.
All types are immutable — frozen=True.

This layer builds structured knowledge about Google Flow's cinematographic
capabilities, camera movements, shot types, storyboard patterns, and
continuity rules.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

# ═══════════════════════════════════════════════════════════════════════════════
# Enumerated Sets
# ═══════════════════════════════════════════════════════════════════════════════

FLOW_MODES: frozenset[str] = frozenset({
    "text_to_video",
    "image_to_video",
    "frame_continuation",
    "ingredients_to_video",
    "extend_mode",
    "jump_to_mode",
    "scene_builder",
})

CAMERA_MOTION_TYPES: frozenset[str] = frozenset({
    "dolly_in",
    "dolly_out",
    "orbit",
    "crane_up",
    "crane_down",
    "handheld",
    "tracking_shot",
    "macro_close_up",
    "push_in",
    "rack_focus",
    "hero_shot",
    "cinematic_pan",
    "parallax_movement",
    "slow_reveal",
    "top_down_rotation",
    "floating_object_orbit",
})

SHOT_TYPES: frozenset[str] = frozenset({
    "hero_shot",
    "macro_detail_shot",
    "emotional_lifestyle_shot",
    "floating_product_shot",
    "transformation_shot",
    "unboxing_shot",
    "cinematic_reveal",
    "comparison_shot",
    "luxury_product_shot",
    "premium_tech_shot",
    "beauty_close_up",
    "kinetic_montage_shot",
})

TRANSITION_TYPES: frozenset[str] = frozenset({
    "match_cut",
    "dissolve",
    "hard_cut",
    "whip_pan",
    "light_flash",
    "motion_blur",
    "product_morph",
    "zoom_transition",
    "mask_reveal",
    "continuous_motion",
})

CONTINUITY_DIMENSIONS: frozenset[str] = frozenset({
    "palette_coherence",
    "product_consistency",
    "lighting_continuity",
    "camera_continuity",
    "object_persistence",
    "motion_smoothness",
    "style_coherence",
    "framing_consistency",
})

LENS_STYLES: frozenset[str] = frozenset({
    "macro",
    "wide_angle",
    "telephoto",
    "standard_prime",
    "anamorphic",
    "cinematic_shallow_dof",
    "fisheye_product",
})

LIGHTING_STYLES: frozenset[str] = frozenset({
    "dark_matte",
    "soft_rim",
    "high_key_commercial",
    "low_key_dramatic",
    "natural_window",
    "golden_hour",
    "studio_three_point",
    "reflective_surface",
    "neon_accent",
    "product_spotlight",
})

ATMOSPHERE_LABELS: frozenset[str] = frozenset({
    "premium_commercial",
    "cinematic_drama",
    "minimal_elegance",
    "warm_lifestyle",
    "tech_futuristic",
    "luxury_dark",
    "bright_ecommerce",
})

PACING_LABELS: frozenset[str] = frozenset({
    "slow_dramatic",
    "medium_commercial",
    "fast_kinetic",
    "variable_rhythm",
})

# ═══════════════════════════════════════════════════════════════════════════════
# Core Schemas
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class FlowFeature:
    """
    Documented knowledge about one Google Flow feature/capability.

    Research-only: documents what the feature does, its limits, and best practices.
    """
    feature_id:      str       # unique slug (e.g., "text_to_video")
    name:            str       # human-readable name
    description:     str       # what this feature does
    mode:            str       # one of FLOW_MODES
    limitations:     tuple[str, ...]   # known constraints
    when_to_use:     tuple[str, ...]   # ideal scenarios
    when_not_to_use: tuple[str, ...]   # anti-patterns
    estimated_cost:  float             # relative cost 0.0–1.0
    drift_risk:      float             # 0.0–1.0 visual drift risk
    best_practices:  tuple[str, ...]   # recommended patterns
    real_examples:   tuple[str, ...]   # anonymized example descriptions

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("limitations", "when_to_use", "when_not_to_use",
                   "best_practices", "real_examples"):
            d[k] = list(d[k])
        return d


@dataclass(frozen=True)
class CameraMotion:
    """
    One camera movement technique for cinematic video generation.

    Documents emotional impact, ideal products, recommended prompts,
    and common mistakes.
    """
    motion_id:           str       # e.g., "dolly_in"
    name:                str       # human-readable
    description:         str
    emotional_feel:      str       # emotional quality (e.g., "intimate", "epic")
    ideal_for:           tuple[str, ...]   # product types
    recommended_speed:   str       # "slow" | "medium" | "fast"
    lighting_pairing:    tuple[str, ...]   # compatible lighting styles
    prompt_template:     str       # reusable prompt pattern
    common_mistakes:     tuple[str, ...]
    example_use:         str       # anonymized example description

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("ideal_for", "lighting_pairing", "common_mistakes"):
            d[k] = list(d[k])
        return d


@dataclass(frozen=True)
class CinematicShot:
    """
    One shot type from the cinematographic taxonomy.

    Defines camera style, lens, lighting, pacing, and motion profile
    for a specific visual intent.
    """
    shot_id:               str       # e.g., "hero_shot"
    name:                  str
    description:           str
    category:              str       # one of SHOT_TYPES
    camera_style:          str       # one of CAMERA_MOTION_TYPES
    lens_style:            str       # one of LENS_STYLES
    lighting_setup:        tuple[str, ...]  # one or more LIGHTING_STYLES
    pacing:                str       # one of PACING_LABELS
    motion_profile:        str       # motion description for prompt
    aesthetic_category:    str       # one of ATMOSPHERE_LABELS
    compatible_transitions: tuple[str, ...]   # TRANSITION_TYPES
    prompt_scaffold:       str       # reusable prompt structure

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("lighting_setup", "compatible_transitions"):
            d[k] = list(d[k])
        return d


@dataclass(frozen=True)
class SceneTransition:
    """
    One scene transition technique for connecting video clips.

    Documents compatibility, emotional impact, and when to use each.
    """
    transition_id:    str
    name:             str
    description:      str
    best_for:         tuple[str, ...]   # shot pairings this works for
    emotional_impact: str
    complexity:       str               # "simple" | "moderate" | "complex"
    drift_risk:       float             # 0.0–1.0
    compatible_shots: tuple[str, ...]   # SHOT_TYPES this pairs with

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("best_for", "compatible_shots"):
            d[k] = list(d[k])
        return d


@dataclass(frozen=True)
class StoryboardStep:
    """
    One shot in a multi-shot storyboard.

    A video is NOT one giant prompt. It is multiple scenes,
    multiple cameras, multiple rhythms, multiple visual intents.
    """
    step_index:       int
    shot_type:        str       # one of SHOT_TYPES
    camera_motion:    str       # one of CAMERA_MOTION_TYPES
    lighting:         str       # one of LIGHTING_STYLES
    pacing:           str       # one of PACING_LABELS
    duration_hint:    str       # "2s" | "3s" | "4s" | "5s"
    intent:           str       # what this shot is meant to communicate
    prompt_fragment:  str       # the prompt text for this shot
    transition_to_next: str = ""  # transition to following shot

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class StoryboardPattern:
    """
    A complete storyboard — a sequence of shots forming a video structure.

    Documents the rhythm, shot count, and overall visual intent.
    """
    pattern_id:      str
    name:            str
    description:     str
    total_shots:     int
    shot_sequence:   tuple[StoryboardStep, ...]
    overall_rhythm:  str       # one of PACING_LABELS
    ideal_for:       tuple[str, ...]   # product categories
    estimated_cost:  float             # relative 0.0–1.0
    risk_level:      str               # "low" | "medium" | "high"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["shot_sequence"] = [s.to_dict() for s in self.shot_sequence]
        d["ideal_for"] = list(self.ideal_for)
        return d


@dataclass(frozen=True)
class ContinuityRule:
    """
    A rule for maintaining visual continuity across scenes.

    Documents how to reuse frames, extend clips, maintain color consistency,
    and avoid motion discontinuity.
    """
    rule_id:         str
    name:            str
    description:     str
    dimension:       str       # one of CONTINUITY_DIMENSIONS
    technique:       str       # how to implement this rule
    failure_mode:    str       # what happens when this rule is violated
    prevention:      str       # how to prevent the failure
    applicable_modes: tuple[str, ...]  # FLOW_MODES this applies to

    def to_dict(self) -> dict:
        d = asdict(self)
        d["applicable_modes"] = list(self.applicable_modes)
        return d


@dataclass(frozen=True)
class ContinuityValidation:
    """
    Result of running continuity validation on a video sequence.

    Non-blocking: scores and warns, never rejects.
    """
    validation_id:   str
    validated_at:    str
    dimensions_checked: tuple[str, ...]   # CONTINUITY_DIMENSIONS
    scores:          dict[str, float]     # dimension → 0.0–1.0
    overall_score:   float               # 0.0–1.0 composite
    warnings:        tuple[str, ...]     # human-readable issues found
    passed:          bool                # overall threshold met

    def to_dict(self) -> dict:
        d = asdict(self)
        d["dimensions_checked"] = list(self.dimensions_checked)
        d["warnings"] = list(self.warnings)
        return d


@dataclass(frozen=True)
class PromptCinematicPattern:
    """
    A reusable cinematic prompt structure template.

    Structure: PRODUCT + CAMERA + LIGHTING + MOTION + ENVIRONMENT
               + LENS STYLE + PACING + ATMOSPHERE
    """
    pattern_id:       str
    name:             str
    description:      str
    structure_order:  tuple[str, ...]  # ordered list of prompt components
    template:         str              # template with {placeholders}
    example_filled:   str              # filled example
    applicable_shots: tuple[str, ...]  # SHOT_TYPES this works for
    strength:         float            # 0.0–1.0 effectiveness rating

    def to_dict(self) -> dict:
        d = asdict(self)
        d["structure_order"] = list(self.structure_order)
        d["applicable_shots"] = list(self.applicable_shots)
        return d


@dataclass(frozen=True)
class FlowUIElement:
    """
    A mapped UI element from Google Flow — button, panel, or control.

    Research-only: documents what exists in the UI for future automation.
    """
    element_id:      str
    name:            str
    ui_location:     str       # where it's found (e.g., "right_panel > camera_tab")
    function:        str       # what it does
    flow_mode:       str       # which FLOW_MODE it appears in
    risks:           tuple[str, ...]
    best_practices:  tuple[str, ...]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["risks"] = list(self.risks)
        d["best_practices"] = list(self.best_practices)
        return d


@dataclass(frozen=True)
class FlowLimitation:
    """
    Documented limitation or constraint of Google Flow.

    Knowing limits prevents wasted generation credits.
    """
    limitation_id:  str
    name:           str
    description:    str
    severity:       str       # "minor" | "moderate" | "critical"
    affected_modes: tuple[str, ...]   # FLOW_MODES impacted
    workaround:     str       # how to mitigate
    credit_impact:  str       # how it affects credit usage

    def to_dict(self) -> dict:
        d = asdict(self)
        d["affected_modes"] = list(self.affected_modes)
        return d


@dataclass(frozen=True)
class CinematicCostEstimate:
    """
    Credit cost estimation for a proposed video generation.

    Helps avoid wasting limited daily generation credits.
    """
    estimate_id:       str
    storyboard_name:   str
    total_shots:       int
    estimated_credits: int
    mode_breakdown:    dict[str, int]     # FLOW_MODE → credits
    risk_level:        str               # "low" | "medium" | "high" | "prohibitive"
    optimization_tips: tuple[str, ...]   # ways to reduce credit usage
    is_viable:         bool              # within daily budget

    def to_dict(self) -> dict:
        d = asdict(self)
        d["optimization_tips"] = list(self.optimization_tips)
        return d


@dataclass(frozen=True)
class CinematicTrainingExample:
    """
    Reference example of a cinematic ad pattern — NO literal content copied.

    Stores structural patterns, pacing, cinematography, composition.
    Only patterns, never actual content.
    """
    example_id:      str
    category:        str       # "luxury_tech" | "cinematic_beauty" | etc.
    shot_count:      int
    dominant_style:  str       # ATMOSPHERE_LABELS
    camera_patterns: tuple[str, ...]   # sequence of CAMERA_MOTION_TYPES
    pacing_pattern:  str       # PACING_LABELS
    hook_structure:  str       # how the ad opens
    composition_notes: tuple[str, ...]  # structural observations
    source_type:     str       # "public_ad" | "reference_study" | "pattern_synthesis"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["camera_patterns"] = list(self.camera_patterns)
        d["composition_notes"] = list(self.composition_notes)
        return d

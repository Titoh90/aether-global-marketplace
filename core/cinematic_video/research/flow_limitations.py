#!/usr/bin/env python3
"""
flow_limitations.py — Documented limitations and constraints of Google Flow.

Knowledge of what Flow CANNOT do well — prevents wasting generation
credits on impossible requests.

RESEARCH-ONLY: No video generation. Pure knowledge.
"""

from __future__ import annotations

from core.cinematic_video.research.schemas import FlowLimitation


_LIMITATIONS: tuple[FlowLimitation, ...] = (
    FlowLimitation(
        limitation_id="max_clip_length",
        name="Maximum Clip Length",
        description=(
            "Text-to-video and image-to-video generations are limited to "
            "approximately 4-8 seconds per clip. Longer videos require "
            "extend mode or clip stitching, which increases credit cost "
            "and drift risk."
        ),
        severity="critical",
        affected_modes=("text_to_video", "image_to_video", "ingredients_to_video"),
        workaround="Use Extend Mode for +2-4s, or stitch multiple clips. Plan storyboards for 4-6s per shot.",
        credit_impact="Each extension costs 0.8-1.0 credits. A 4-clip sequence = 4-6 credits minimum.",
    ),
    FlowLimitation(
        limitation_id="style_drift_accumulation",
        name="Style Drift Accumulation",
        description=(
            "Visual style degrades across multiple generations. Each new clip "
            "in a sequence has higher drift risk. After 3+ clips, style "
            "coherence becomes unreliable without strong reference anchoring."
        ),
        severity="critical",
        affected_modes=("text_to_video", "frame_continuation", "extend_mode"),
        workaround=(
            "Use image_to_video with last frame as anchor for every clip. "
            "Limit sequences to 4-5 shots max. Use identical style anchor "
            "phrase in every prompt."
        ),
        credit_impact="Mitigation costs 0 extra credits (just prompt discipline), but limits sequence length.",
    ),
    FlowLimitation(
        limitation_id="exact_product_fidelity_text_only",
        name="Exact Product Fidelity (Text-Only)",
        description=(
            "Text-to-video cannot guarantee exact product appearance. "
            "The AI interprets product descriptions creatively. For "
            "brand-accurate products, image_to_video is required."
        ),
        severity="critical",
        affected_modes=("text_to_video",),
        workaround="Always use image_to_video as the anchor shot for product-critical content.",
        credit_impact="Image-to-video costs same as text-to-video (1.0 credits), but requires preparing reference images.",
    ),
    FlowLimitation(
        limitation_id="complex_multi_subject_scenes",
        name="Complex Multi-Subject Scenes",
        description=(
            "Prompts describing multiple subjects, complex environments, "
            "or detailed interactions often produce inconsistent results. "
            "Flow works best with ONE clear subject per clip."
        ),
        severity="moderate",
        affected_modes=("text_to_video", "image_to_video"),
        workaround="Keep clips focused on ONE product or ONE interaction. Split complex scenes into multiple shots.",
        credit_impact="Splitting complex scenes into multiple shots increases total credit usage.",
    ),
    FlowLimitation(
        limitation_id="frame_accurate_timing",
        name="Frame-Accurate Timing",
        description=(
            "Flow does not support frame-accurate timing control. "
            "You cannot specify 'hold product for exactly 2.3 seconds' "
            "or 'transition at frame 47'."
        ),
        severity="moderate",
        affected_modes=("text_to_video", "image_to_video", "frame_continuation", "extend_mode", "scene_builder"),
        workaround="Use external video editing tools (FFmpeg, DaVinci) for frame-accurate timing. Flow for generation only.",
        credit_impact="No credit impact — this is a post-generation editing concern.",
    ),
    FlowLimitation(
        limitation_id="product_transformations_unreliable",
        name="Product Transformations (Unreliable)",
        description=(
            "Asking Flow to transform one product into another (color change, "
            "shape morph, material change) often produces glitchy or "
            "unconvincing results."
        ),
        severity="moderate",
        affected_modes=("text_to_video", "image_to_video"),
        workaround="Generate separate clips for each state and use external morphing/blending tools.",
        credit_impact="Separate clips = more credits, but also more reliable results.",
    ),
    FlowLimitation(
        limitation_id="text_and_ui_in_video",
        name="Text and UI in Video",
        description=(
            "Flow cannot reliably generate readable text, logos, or UI elements "
            "within generated videos. Text appears garbled or nonsensical."
        ),
        severity="critical",
        affected_modes=("text_to_video", "image_to_video", "scene_builder"),
        workaround="Add text, logos, and UI overlays in post-production using external tools. Flow for visuals only.",
        credit_impact="None — text overlay is always post-production.",
    ),
    FlowLimitation(
        limitation_id="audio_not_handled",
        name="Audio Not Handled by Flow",
        description=(
            "Flow does not generate or sync audio. Music, voiceover, "
            "and sound effects must be added in post-production."
        ),
        severity="minor",
        affected_modes=("text_to_video", "image_to_video", "frame_continuation",
                         "extend_mode", "ingredients_to_video", "scene_builder"),
        workaround="Use external audio tools (ElevenLabs for voice, Artlist for music). Add audio in video editor.",
        credit_impact="No credit impact — audio is separate workflow.",
    ),
    FlowLimitation(
        limitation_id="daily_generation_limits",
        name="Daily Generation Limits",
        description=(
            "Flow has daily credit limits that vary by account tier. "
            "Complex multi-clip projects can exceed daily limits, "
            "requiring multi-day generation sessions."
        ),
        severity="critical",
        affected_modes=("text_to_video", "image_to_video", "frame_continuation",
                         "extend_mode", "ingredients_to_video", "scene_builder"),
        workaround=(
            "Plan credit budget BEFORE generating. Use cost estimator. "
            "Prioritize image_to_video for product-critical shots. "
            "Save credits by reusing frames instead of new generations."
        ),
        credit_impact="Fundamental constraint — plan around daily limits.",
    ),
    FlowLimitation(
        limitation_id="inconsistent_camera_controls",
        name="Inconsistent Camera Controls",
        description=(
            "Camera motion parameters (speed, smoothness, exact path) "
            "are interpreted by AI, not executed precisely. Results vary "
            "between generations even with identical prompts."
        ),
        severity="moderate",
        affected_modes=("text_to_video", "image_to_video"),
        workaround="Generate multiple takes and pick the best. Use image_to_video for more controlled results.",
        credit_impact="Multiple takes = multiple credits. Budget 1-2 extra credits per shot for retakes.",
    ),
    FlowLimitation(
        limitation_id="high_resolution_limitations",
        name="High Resolution Limitations",
        description=(
            "Generated video resolution may be lower than source images. "
            "Frame exports may lose quality. Not suitable for 4K+ "
            "production without external upscaling."
        ),
        severity="moderate",
        affected_modes=("text_to_video", "image_to_video", "frame_continuation"),
        workaround="Use external AI upscalers (Topaz, Real-ESRGAN) for final output quality.",
        credit_impact="No credit impact — post-production concern.",
    ),
    FlowLimitation(
        limitation_id="background_complexity_issues",
        name="Background Complexity Issues",
        description=(
            "Complex, busy, or highly detailed backgrounds often produce "
            "artifacts, inconsistent elements, or distracting motion. "
            "Simple, clean backgrounds work much better."
        ),
        severity="minor",
        affected_modes=("text_to_video", "image_to_video"),
        workaround="Use minimal backgrounds: 'dark void', 'clean white surface', 'reflective obsidian'.",
        credit_impact="No extra cost — just prompt discipline.",
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_limitations() -> tuple[FlowLimitation, ...]:
    """Return all documented limitations."""
    return _LIMITATIONS


def get_limitation(limitation_id: str) -> FlowLimitation | None:
    """Look up a limitation by ID."""
    for l in _LIMITATIONS:
        if l.limitation_id == limitation_id:
            return l
    return None


def get_critical_limitations() -> tuple[FlowLimitation, ...]:
    """Only critical-severity limitations."""
    return tuple(l for l in _LIMITATIONS if l.severity == "critical")


def get_limitations_by_mode(mode: str) -> tuple[FlowLimitation, ...]:
    """Limitations affecting a specific Flow mode."""
    return tuple(l for l in _LIMITATIONS if mode in l.affected_modes)


def limitation_count() -> int:
    return len(_LIMITATIONS)

#!/usr/bin/env python3
"""
flow_feature_registry.py — Complete registry of Google Flow features.

Documents all 14 generation capabilities with descriptions, limitations,
best practices, and estimated costs. RESEARCH-ONLY — no generation calls.

Rules:
- NO video generation
- NO API calls
- Pure knowledge documentation
"""

from __future__ import annotations

from core.cinematic_video.research.schemas import FlowFeature


# ═══════════════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════════════

_FLOW_FEATURES: tuple[FlowFeature, ...] = (
    # ── 1. Text-to-Video ─────────────────────────────────────────────────
    FlowFeature(
        feature_id="text_to_video",
        name="Text-to-Video",
        description=(
            "Generates a video clip directly from a text prompt. "
            "The primary entry point for cinematic ad creation. "
            "Output length typically 4-8 seconds. "
            "Supports camera control, lighting, and motion keywords in prompt."
        ),
        mode="text_to_video",
        limitations=(
            "Limited to ~8s maximum per generation",
            "Prompt weight decreases for complex multi-subject scenes",
            "Style consistency degrades with very long prompts",
            "Cannot guarantee exact product appearance from text alone",
            "Credit cost: 1 generation per clip",
        ),
        when_to_use=(
            "When you have a strong prompt with camera + lighting + motion",
            "For establishing shots and hero product reveals",
            "When no reference image is available",
            "For abstract/environment-focused shots",
        ),
        when_not_to_use=(
            "When exact product matching is critical — use image_to_video",
            "For sequences longer than 8s — use extend_mode",
            "When you need frame-accurate timing",
            "For multi-product comparison shots",
        ),
        estimated_cost=1.0,
        drift_risk=0.4,
        best_practices=(
            "Structure: PRODUCT + CAMERA + LIGHTING + MOTION + ENVIRONMENT + LENS + PACING + ATMOSPHERE",
            "Keep prompts under 200 characters for best style adherence",
            "Use cinematic keywords: 'cinematic commercial', 'premium advertisement'",
            "Add quality anchors: 'ultra realistic', 'high-end product photography'",
            "Specify aspect ratio when possible (e.g., 'vertical 9:16')",
        ),
        real_examples=(
            "Luxury watch: 'cinematic commercial of matte black watch, floating above obsidian, dark luxury lighting, slow orbit, macro lens, premium ad aesthetic'",
            "Skincare: 'ultra cinematic shot of glass serum bottle, soft rim light, dewdrops on surface, push-in camera, shallow depth of field, premium beauty commercial'",
        ),
    ),

    # ── 2. Image-to-Video ────────────────────────────────────────────────
    FlowFeature(
        feature_id="image_to_video",
        name="Image-to-Video",
        description=(
            "Generates a video clip starting from a reference image. "
            "The image provides the product/subject anchor, and the prompt "
            "describes the camera movement, lighting, and environment. "
            "Much higher product fidelity than text-to-video."
        ),
        mode="image_to_video",
        limitations=(
            "Requires a high-quality reference image",
            "Image must be well-lit and clearly composed",
            "Background in reference image may constrain generation",
            "Product proportions from reference are largely preserved",
            "Credit cost: 1 generation + 1 image upload",
        ),
        when_to_use=(
            "When you have a product photo and need cinematic motion",
            "For product-specific shots where brand accuracy matters",
            "As the anchor shot in a multi-clip sequence",
            "When you need to guarantee product appearance",
        ),
        when_not_to_use=(
            "When the reference image is low quality or poorly lit",
            "For establishing shots without a product",
            "When you want dramatic product transformations",
            "For abstract concept videos without a physical product",
        ),
        estimated_cost=1.0,
        drift_risk=0.2,
        best_practices=(
            "Use clean product-on-white or product-on-dark photos",
            "Remove busy backgrounds before uploading",
            "Match prompt lighting to image lighting",
            "Start with simpler motions (orbit, push-in) before complex ones",
            "Use image-to-video as the anchor, then extend for additional shots",
        ),
        real_examples=(
            "Product photo → 'slow orbit around product, dark luxury lighting, cinematic commercial aesthetic'",
            "Flat lay image → 'crane up reveal, soft commercial lighting, shallow depth of field, premium product presentation'",
        ),
    ),

    # ── 3. Frame Continuation ────────────────────────────────────────────
    FlowFeature(
        feature_id="frame_continuation",
        name="Frame Continuation",
        description=(
            "Extends a video from its last frame, continuing the motion "
            "and visual style. Essential for building multi-shot sequences "
            "without visible cuts or style breaks."
        ),
        mode="frame_continuation",
        limitations=(
            "Each continuation = 1 credit",
            "Drift accumulates over multiple continuations (3+ starts degrading)",
            "Cannot change product appearance mid-sequence",
            "Motion direction continues from previous clip",
            "Limited to ~4-6s per continuation",
        ),
        when_to_use=(
            "To extend a shot beyond the 8s limit",
            "To build smooth multi-angle sequences",
            "When you need a continuous camera movement across shots",
            "For slow reveal sequences",
        ),
        when_not_to_use=(
            "For hard cuts between completely different scenes — use separate generations",
            "When you've already done 3+ continuations (drift risk too high)",
            "For product transformations or scene changes",
            "When credit budget is very tight",
        ),
        estimated_cost=1.0,
        drift_risk=0.6,
        best_practices=(
            "Limit to 2-3 continuations max per sequence",
            "Validate color palette between continuations",
            "Use simpler camera motions in continuations",
            "End on a stable frame before continuation",
            "Avoid continuation after fast/erratic camera movements",
        ),
        real_examples=(
            "Orbit shot 1 (left side) → continuation to orbit shot 2 (right side)",
            "Push-in from wide to medium → continuation for close-up detail",
        ),
    ),

    # ── 4. Ingredients-to-Video ──────────────────────────────────────────
    FlowFeature(
        feature_id="ingredients_to_video",
        name="Ingredients-to-Video",
        description=(
            "Generates a video using multiple input 'ingredients' — typically "
            "a reference image AND a text prompt. The image anchors the subject "
            "while the prompt controls motion and style."
        ),
        mode="ingredients_to_video",
        limitations=(
            "Not all Flow instances support ingredients mode",
            "Ingredient weighting can be inconsistent",
            "Multiple ingredients increase generation time",
            "Complex ingredient combinations may produce unexpected results",
        ),
        when_to_use=(
            "When you want image fidelity + creative camera motion",
            "For shots that reference a product but need atmospheric context",
            "When blending product image with style reference",
            "For shots where text alone can't describe the product accurately",
        ),
        when_not_to_use=(
            "When a simple image-to-video would suffice",
            "When ingredients conflict (dark + bright references)",
            "For rapid iteration — ingredients mode is slower",
        ),
        estimated_cost=1.2,
        drift_risk=0.3,
        best_practices=(
            "Use one clear product image + one style prompt",
            "Keep ingredients consistent in lighting and tone",
            "Test with simple ingredient combos before complex ones",
            "Document successful ingredient pairings",
        ),
        real_examples=(
            "Product image + 'cinematic floating product, dark reflective surface, luxury commercial aesthetic'",
        ),
    ),

    # ── 5. Extend Mode ───────────────────────────────────────────────────
    FlowFeature(
        feature_id="extend_mode",
        name="Extend Mode",
        description=(
            "Extends an existing video clip beyond its original duration. "
            "The AI generates additional frames that continue the visual "
            "style and motion of the original clip."
        ),
        mode="extend_mode",
        limitations=(
            "Style drift increases with each extension",
            "Cannot reverse or change motion direction easily",
            "Original clip quality affects extension quality",
            "Credit cost is per extension, not per second",
        ),
        when_to_use=(
            "To lengthen a shot that ended too early",
            "To add breathing room at the end of a clip",
            "When you need a few more seconds of the same motion",
            "For slow, continuous camera moves that need more time",
        ),
        when_not_to_use=(
            "To change the camera direction or shot type",
            "When the original clip already shows drift",
            "For multi-extension sequences (use frame_continuation instead)",
            "When you need a fundamentally different shot",
        ),
        estimated_cost=0.8,
        drift_risk=0.5,
        best_practices=(
            "Extend from a stable, well-composed frame",
            "Use for 2-4s extensions, not major additions",
            "Validate after extension — drift can be subtle",
            "Prefer frame_continuation for multi-shot building",
        ),
        real_examples=(
            "4s orbit clip → extend 2s to complete the rotation",
            "Product reveal that ends abruptly → extend for a beat of stillness",
        ),
    ),

    # ── 6. Jump-to Mode ──────────────────────────────────────────────────
    FlowFeature(
        feature_id="jump_to_mode",
        name="Jump-to Mode",
        description=(
            "Allows jumping to a specific frame position in a generated "
            "clip to continue generation from that point. Useful for "
            "recovering from generation errors or creating precise edits."
        ),
        mode="jump_to_mode",
        limitations=(
            "Only works on generated clips, not uploaded videos",
            "Jump position accuracy is approximate",
            "May break continuity if jumped too far",
            "Not all Flow versions support this",
        ),
        when_to_use=(
            "To fix a specific segment that generated poorly",
            "To create precise edit points in a sequence",
            "When the last 2s of a clip are good but the first part isn't",
            "For recovering partial generations",
        ),
        when_not_to_use=(
            "As a primary workflow — adds complexity",
            "For minor issues that don't justify the credit cost",
            "When frame accuracy is critical (it's approximate)",
        ),
        estimated_cost=0.7,
        drift_risk=0.4,
        best_practices=(
            "Use sparingly — prefer re-generation for major issues",
            "Jump to natural transition points, not mid-motion",
            "Validate continuity after jump-to",
            "Document jump positions for reproducibility",
        ),
        real_examples=(
            "First 3s of orbit look good, last 2s drift → jump to 3s mark and re-generate ending",
        ),
    ),

    # ── 7. Scene Builder ─────────────────────────────────────────────────
    FlowFeature(
        feature_id="scene_builder",
        name="Scene Builder",
        description=(
            "A dedicated mode for constructing multi-scene sequences. "
            "Allows planning shot order, transitions, and visual continuity "
            "across a complete video composition."
        ),
        mode="scene_builder",
        limitations=(
            "Not available on all Flow tiers",
            "Scene count may be limited (typically 4-6 scenes)",
            "Each scene = 1 credit minimum",
            "Scene transitions can be inconsistent",
            "Complex storyboards may exceed credit limits",
        ),
        when_to_use=(
            "For complete video ads with multiple shots",
            "When you need planned scene progression",
            "For narrative sequences (intro → body → climax → CTA)",
            "When you want Flow to handle transition logic",
        ),
        when_not_to_use=(
            "For single-shot videos",
            "When manual clip stitching gives better control",
            "For very complex storyboards (>6 scenes)",
            "When credit budget is under 5",
        ),
        estimated_cost=1.5,
        drift_risk=0.5,
        best_practices=(
            "Plan storyboard COMPLETELY before entering Scene Builder",
            "Keep scenes simple — one camera motion per scene",
            "Use consistent lighting across all scenes",
            "Build in pairs: odd scenes = product, even scenes = lifestyle/context",
            "Save/reuse successful scene templates",
        ),
        real_examples=(
            "4-scene ad: Scene 1 (hero macro) → Scene 2 (lifestyle context) → Scene 3 (floating product) → Scene 4 (CTA + logo)",
        ),
    ),

    # ── 8. Camera Controls ───────────────────────────────────────────────
    FlowFeature(
        feature_id="camera_controls",
        name="Camera Controls",
        description=(
            "Direct camera movement controls within Flow. "
            "Includes orbit, dolly, crane, pan, and push-in/pull-out. "
            "Can be specified in prompts or via UI controls."
        ),
        mode="text_to_video",
        limitations=(
            "UI camera controls may not be available in all modes",
            "Complex multi-axis movements may glitch",
            "Speed control is approximate, not frame-accurate",
            "Some movements require image-to-video for best results",
        ),
        when_to_use=(
            "For EVERY cinematic ad — camera motion is essential",
            "To add production value to product shots",
            "To create visual interest in otherwise static scenes",
        ),
        when_not_to_use=(
            "When the product is best shown static (rare)",
            "For text-heavy or UI-focused videos",
        ),
        estimated_cost=0.0,  # no extra cost — part of prompt
        drift_risk=0.1,
        best_practices=(
            "One primary camera motion per shot",
            "Match motion speed to product type (slow for luxury, medium for tech)",
            "Combine camera motion with lighting for cinematic depth",
            "Test motions individually before combining",
        ),
        real_examples=(
            "'slow orbit' for luxury watches",
            "'push-in macro' for detail shots",
            "'crane up reveal' for product unveiling",
        ),
    ),

    # ── 9. Frame Export ──────────────────────────────────────────────────
    FlowFeature(
        feature_id="frame_export",
        name="Frame Export",
        description=(
            "Exports individual frames from generated videos as still images. "
            "Crucial for creating reference images for image-to-video, "
            "building continuity chains, and archiving successful compositions."
        ),
        mode="text_to_video",
        limitations=(
            "Export resolution may be lower than original generation",
            "Not all frames are equally suitable (motion blur frames)",
            "Export format may be limited (JPG vs PNG)",
        ),
        when_to_use=(
            "To capture the last frame for frame_continuation",
            "To create reference images for image_to_video",
            "To archive successful compositions for reuse",
            "To build an ingredient library",
        ),
        when_not_to_use=(
            "For final output — export the video instead",
            "When the frame has motion blur or artifacts",
            "For bulk export (may hit rate limits)",
        ),
        estimated_cost=0.0,
        drift_risk=0.0,
        best_practices=(
            "Export last frame of each successful clip for continuity",
            "Choose frames at rest (end of camera movement)",
            "Build a frame library organized by product + style",
            "Label exports clearly: product_shot_camera_lighting",
        ),
        real_examples=(
            "End frame of orbit shot → export → use as reference for next scene",
            "Best frame of macro detail → export → use for ingredient-based generation",
        ),
    ),

    # ── 10. Aspect Ratio Controls ────────────────────────────────────────
    FlowFeature(
        feature_id="aspect_ratio_controls",
        name="Aspect Ratio Controls",
        description=(
            "Controls for setting output aspect ratio: 1:1 (square), "
            "4:5 (portrait), 9:16 (vertical/stories), 16:9 (landscape). "
            "Critical for platform-specific ad formats."
        ),
        mode="text_to_video",
        limitations=(
            "Some aspect ratios may crop the generated scene",
            "Not all ratios available in all modes",
            "Vertical (9:16) may have different quality than landscape",
            "Ratio changes may affect composition quality",
        ),
        when_to_use=(
            "ALWAYS specify aspect ratio in prompt",
            "9:16 for Instagram Reels, TikTok, YouTube Shorts",
            "1:1 for Instagram feed posts",
            "16:9 for YouTube ads, website hero videos",
        ),
        when_not_to_use=(
            "Never omit aspect ratio — always specify",
        ),
        estimated_cost=0.0,
        drift_risk=0.0,
        best_practices=(
            "Specify in prompt: 'vertical 9:16' or 'cinematic 16:9'",
            "Compose for the target ratio (center product for 9:16)",
            "Test both vertical and square for cross-platform use",
            "Plan storyboard scenes for target aspect ratio",
        ),
        real_examples=(
            "'vertical 9:16 cinematic commercial of...'",
            "'square 1:1 product shot, centered composition...'",
        ),
    ),

    # ── 11. Motion Intensity ─────────────────────────────────────────────
    FlowFeature(
        feature_id="motion_intensity",
        name="Motion Intensity",
        description=(
            "Controls the intensity/speed of camera movement. "
            "Can be specified via prompt keywords ('slow orbit', 'fast pan') "
            "or potentially via UI slider."
        ),
        mode="text_to_video",
        limitations=(
            "Intensity interpretation is subjective and inconsistent",
            "Extreme intensities (very fast/slow) may produce artifacts",
            "UI slider not always available",
        ),
        when_to_use=(
            "Slow: luxury products, detail shots, emotional moments",
            "Medium: lifestyle shots, product demonstrations",
            "Fast: kinetic montages, energy products, action shots",
        ),
        when_not_to_use=(
            "Fast motion for detailed products (blur ruins detail)",
            "Very slow motion for short clips (<4s — not enough time)",
        ),
        estimated_cost=0.0,
        drift_risk=0.2,
        best_practices=(
            "Match intensity to product personality",
            "Luxury = slow and deliberate",
            "Tech = medium and precise",
            "Lifestyle/fashion = variable rhythm",
            "Always specify speed in prompt: 'slow', 'gentle', 'fast'",
        ),
        real_examples=(
            "'slow deliberate orbit' for luxury watch",
            "'energetic tracking shot' for sports product",
        ),
    ),

    # ── 12. Style Consistency ────────────────────────────────────────────
    FlowFeature(
        feature_id="style_consistency",
        name="Style Consistency",
        description=(
            "Flow's ability to maintain visual style across generations. "
            "Using consistent prompt structures and reference images "
            "improves cross-clip coherence."
        ),
        mode="text_to_video",
        limitations=(
            "Style consistency is NOT guaranteed across separate generations",
            "Drift increases with each new generation",
            "Different camera motions can change the look",
            "No built-in style-lock feature",
        ),
        when_to_use=(
            "Use consistent prompt templates for all clips in a sequence",
            "Reuse anchor phrases: 'cinematic commercial', 'premium aesthetic'",
            "Reference same lighting style across all shots",
        ),
        when_not_to_use=(
            "Don't expect perfect consistency without reference images",
            "Don't mix drastically different styles in one sequence",
        ),
        estimated_cost=0.0,
        drift_risk=0.5,
        best_practices=(
            "Create a style anchor phrase and use it in EVERY prompt",
            "Use image-to-video as the first shot to lock the look",
            "Export and reuse frames for continuity",
            "Validate palette coherence between clips",
            "Limit per-sequence shot count to reduce accumulated drift",
        ),
        real_examples=(
            "Anchor: 'dark luxury cinematic commercial, ultra realistic, premium product advertisement'",
        ),
    ),

    # ── 13. Prompt Weighting ─────────────────────────────────────────────
    FlowFeature(
        feature_id="prompt_weighting",
        name="Prompt Weighting",
        description=(
            "The relative influence of different parts of your prompt "
            "on the generated output. Earlier terms typically have "
            "more weight. Some Flow versions support explicit weighting."
        ),
        mode="text_to_video",
        limitations=(
            "Weighting behavior is not well documented",
            "Explicit weighting syntax may not work",
            "Very long prompts dilute all weights",
            "Conflicting terms produce unpredictable results",
        ),
        when_to_use=(
            "Put most important elements FIRST in prompt",
            "Product description before camera motion",
            "Style anchors early in prompt",
        ),
        when_not_to_use=(
            "Don't rely on undocumented weighting syntax",
            "Don't use very long prompts (>250 chars) — dilution",
        ),
        estimated_cost=0.0,
        drift_risk=0.1,
        best_practices=(
            "Structure: [PRODUCT] [STYLE] [CAMERA] [LIGHTING] [DETAILS]",
            "Keep prompts concise — 100-200 characters ideal",
            "Repeat key style words once (not more — doesn't help)",
            "Test prompt order variations to understand weighting",
        ),
        real_examples=(
            "Good: 'matte black electric trimmer, dark luxury cinematic commercial, slow orbit, macro lens, premium aesthetic'",
            "Bad: too long, key terms buried at end",
        ),
    ),

    # ── 14. Clip Stitching Workflows ─────────────────────────────────────
    FlowFeature(
        feature_id="clip_stitching_workflows",
        name="Clip Stitching Workflows",
        description=(
            "Patterns for combining multiple generated clips into "
            "a single coherent video. Flow provides basic stitching; "
            "complex assembly may require external video editing."
        ),
        mode="scene_builder",
        limitations=(
            "Flow's built-in stitching is basic",
            "Cross-clip color grading may be needed externally",
            "Audio sync not handled by Flow",
            "Transition quality varies between clip pairs",
        ),
        when_to_use=(
            "For simple 2-4 clip sequences",
            "When clips share the same style anchor",
            "For rapid prototyping of ad structure",
        ),
        when_not_to_use=(
            "For complex multi-angle sequences (use external editor)",
            "When precise frame-accurate cuts are needed",
            "For final delivery without external polish",
        ),
        estimated_cost=0.3,
        drift_risk=0.3,
        best_practices=(
            "Generate all clips with the same style anchor",
            "Use frame export from clip N as reference for clip N+1",
            "Plan transitions BEFORE generating",
            "Validate stitched output — check for jump cuts",
            "Consider external tools (FFmpeg, DaVinci) for final assembly",
        ),
        real_examples=(
            "Flow stitch: Scene 1 (image-to-video hero) → Scene 2 (text-to-video lifestyle) → Scene 3 (extend with CTA frame)",
        ),
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_features() -> tuple[FlowFeature, ...]:
    """Return all documented Flow features."""
    return _FLOW_FEATURES


def get_feature(feature_id: str) -> FlowFeature | None:
    """Look up a single feature by ID."""
    for f in _FLOW_FEATURES:
        if f.feature_id == feature_id:
            return f
    return None


def get_features_by_mode(mode: str) -> tuple[FlowFeature, ...]:
    """Get features relevant to a specific Flow mode."""
    return tuple(f for f in _FLOW_FEATURES if f.mode == mode)


def get_high_risk_features() -> tuple[FlowFeature, ...]:
    """Features with drift_risk >= 0.5."""
    return tuple(f for f in _FLOW_FEATURES if f.drift_risk >= 0.5)


def get_credit_efficient_features() -> tuple[FlowFeature, ...]:
    """Features with estimated_cost <= 0.5."""
    return tuple(f for f in _FLOW_FEATURES if f.estimated_cost <= 0.5)


def feature_count() -> int:
    return len(_FLOW_FEATURES)

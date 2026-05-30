#!/usr/bin/env python3
"""
continuity_rules.py — Visual continuity rules for multi-clip cinematic sequences.

8 continuity rules covering palette, product, lighting, camera, object,
motion, style, and framing consistency across video clips.

RESEARCH-ONLY: No video generation. Pure knowledge.
"""

from __future__ import annotations

from core.cinematic_video.research.schemas import ContinuityRule


_CONTINUITY_RULES: tuple[ContinuityRule, ...] = (
    ContinuityRule(
        rule_id="reuse_last_frame",
        name="Reuse Last Frame as Reference",
        description=(
            "Export the last frame of clip N and use it as the reference image "
            "for clip N+1 (via image_to_video). This anchors the next generation "
            "to the visual state of the previous clip."
        ),
        dimension="palette_coherence",
        technique=(
            "1. Generate clip N. "
            "2. Export last frame via Frame Export. "
            "3. Use exported frame as input to image_to_video for clip N+1. "
            "4. Match prompt lighting/style keywords to clip N."
        ),
        failure_mode="Without frame reference, clip N+1 may have different color temperature, contrast, or product appearance.",
        prevention="Always use last-frame-as-reference for adjacent clips in a sequence.",
        applicable_modes=("image_to_video", "frame_continuation", "ingredients_to_video"),
    ),
    ContinuityRule(
        rule_id="extend_clips_correctly",
        name="Extend Clips Without Breaking Continuity",
        description=(
            "Use Extend Mode to lengthen a clip beyond its original duration "
            "while maintaining motion and style continuity."
        ),
        dimension="motion_smoothness",
        technique=(
            "1. Ensure clip ends on a stable, well-composed frame. "
            "2. Use Extend Mode (not a new generation) for 2-4s additions. "
            "3. Keep extension prompt consistent with original prompt. "
            "4. Limit to 1-2 extensions per clip max."
        ),
        failure_mode="Multiple extensions cause accumulated drift — motion becomes erratic, style degrades.",
        prevention="Plan shot durations BEFORE generating. Avoid needing extensions in the first place.",
        applicable_modes=("extend_mode",),
    ),
    ContinuityRule(
        rule_id="color_consistency",
        name="Maintain Color Consistency",
        description=(
            "Keep color palette, temperature, and saturation consistent across "
            "all clips in a video sequence."
        ),
        dimension="palette_coherence",
        technique=(
            "1. Use the same lighting keywords in all prompts. "
            "2. Reference the same style anchor phrase in every prompt. "
            "3. Avoid mixing warm and cool lighting in one sequence. "
            "4. Use image_to_video with last frame for color anchoring."
        ),
        failure_mode="Color mismatch between clips creates jarring, amateur-looking transitions.",
        prevention="Define a style anchor phrase: 'dark luxury cinematic commercial, ultra realistic' — use verbatim in every prompt.",
        applicable_modes=("text_to_video", "image_to_video", "frame_continuation", "ingredients_to_video", "scene_builder"),
    ),
    ContinuityRule(
        rule_id="avoid_motion_discontinuity",
        name="Avoid Motion Discontinuity",
        description=(
            "Camera motion should flow naturally across clips. Sudden changes "
            "in direction, speed, or type break immersion."
        ),
        dimension="motion_smoothness",
        technique=(
            "1. Plan camera motion sequence BEFORE generating. "
            "2. Orbit direction should be consistent (always clockwise). "
            "3. Speed should be consistent across clips (all 'slow'). "
            "4. Use continuous_motion transition for unbroken camera moves."
        ),
        failure_mode="Orbit reverses direction between clips — disorienting. Push-in followed by pull-out without reason.",
        prevention="Document the planned camera motion sequence. Stick to it. No improvisation between clips.",
        applicable_modes=("text_to_video", "image_to_video", "frame_continuation", "extend_mode"),
    ),
    ContinuityRule(
        rule_id="lighting_continuity",
        name="Maintain Lighting Continuity",
        description=(
            "Lighting direction, quality, and intensity should be consistent "
            "across all shots in a sequence."
        ),
        dimension="lighting_continuity",
        technique=(
            "1. Choose ONE lighting style for the entire sequence. "
            "2. Use the exact same lighting keywords in all prompts. "
            "3. If changing lighting, do it as a deliberate transition (dissolve). "
            "4. Validate rim light direction across clips."
        ),
        failure_mode="Key light moves from left to right between clips — product looks inconsistent.",
        prevention="Document lighting setup: 'soft rim light from upper right, dark matte background'. Use verbatim.",
        applicable_modes=("text_to_video", "image_to_video", "frame_continuation", "ingredients_to_video", "scene_builder"),
    ),
    ContinuityRule(
        rule_id="connect_scenes_without_jump_cuts",
        name="Connect Scenes Without Jump Cuts",
        description=(
            "Avoid jarring visual jumps between scenes. Use appropriate "
            "transitions matched to the content and pacing."
        ),
        dimension="style_coherence",
        technique=(
            "1. Match transition to content: dissolve for luxury, hard cut for energy. "
            "2. Never use hard cuts between slow, elegant shots. "
            "3. Use match_cut when compositions are similar. "
            "4. Validate transition after stitching."
        ),
        failure_mode="Hard cut between two slow orbit shots looks accidental. Dissolve in fast montage kills energy.",
        prevention="Plan transitions during storyboard phase. Document: Shot N → [transition] → Shot N+1.",
        applicable_modes=("text_to_video", "image_to_video", "scene_builder"),
    ),
    ContinuityRule(
        rule_id="reuse_ingredients",
        name="Reuse Frame Ingredients",
        description=(
            "Save and reuse exported frames as 'ingredients' for consistent "
            "visual anchoring across multiple generations."
        ),
        dimension="object_persistence",
        technique=(
            "1. Export best frames from successful generations. "
            "2. Build an ingredient library organized by product + style. "
            "3. Reuse the same ingredient image for all clips of the same product. "
            "4. Update ingredients when better frames are generated."
        ),
        failure_mode="Using different reference images for the same product — product looks slightly different in each clip.",
        prevention="One product = one master reference image. Generate variations FROM that reference.",
        applicable_modes=("ingredients_to_video", "image_to_video", "frame_continuation"),
    ),
    ContinuityRule(
        rule_id="preserve_composition_visual",
        name="Preserve Visual Composition",
        description=(
            "Composition rules (rule of thirds, centering, negative space) "
            "should be consistent across clips for a coherent look."
        ),
        dimension="framing_consistency",
        technique=(
            "1. Decide composition strategy BEFORE generating: centered vs rule of thirds. "
            "2. Include composition keywords in prompt: 'centered composition', 'rule of thirds'. "
            "3. Same product = same framing approach across all clips. "
            "4. Validate composition consistency after generation."
        ),
        failure_mode="Product centered in clip 1, off-center in clip 2 — looks sloppy and unplanned.",
        prevention="Document composition rule in storyboard: all hero shots centered, lifestyle shots rule of thirds.",
        applicable_modes=("text_to_video", "image_to_video", "ingredients_to_video"),
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_rules() -> tuple[ContinuityRule, ...]:
    """Return all 8 continuity rules."""
    return _CONTINUITY_RULES


def get_rule(rule_id: str) -> ContinuityRule | None:
    """Look up a rule by ID."""
    for r in _CONTINUITY_RULES:
        if r.rule_id == rule_id:
            return r
    return None


def get_rules_by_dimension(dimension: str) -> tuple[ContinuityRule, ...]:
    """Get rules for a specific continuity dimension."""
    return tuple(r for r in _CONTINUITY_RULES if r.dimension == dimension)


def get_rules_for_mode(mode: str) -> tuple[ContinuityRule, ...]:
    """Get continuity rules applicable to a specific Flow mode."""
    return tuple(r for r in _CONTINUITY_RULES if mode in r.applicable_modes)


def rule_count() -> int:
    return len(_CONTINUITY_RULES)

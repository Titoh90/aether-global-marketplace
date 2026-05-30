#!/usr/bin/env python3
"""
storyboard_patterns.py — Multi-shot storyboard intelligence.

Teaches the agent: A VIDEO IS NOT ONE GIANT PROMPT.
A video is multiple scenes, multiple cameras, multiple rhythms,
multiple visual intents.

RESEARCH-ONLY: No video generation. Pure knowledge.
"""

from __future__ import annotations

from core.cinematic_video.research.schemas import StoryboardStep, StoryboardPattern


def _mk_shots(*descriptions: tuple[int, str, str, str, str, str, str, str]) -> tuple[StoryboardStep, ...]:
    """Build storyboard steps from compact tuples."""
    steps: list[StoryboardStep] = []
    for step_idx, shot, cam, light, pace, dur, intent, prompt in descriptions:
        steps.append(StoryboardStep(
            step_index=step_idx,
            shot_type=shot,
            camera_motion=cam,
            lighting=light,
            pacing=pace,
            duration_hint=dur,
            intent=intent,
            prompt_fragment=prompt,
            transition_to_next="dissolve" if step_idx < len(descriptions) else "",
        ))
    return tuple(steps)


_STORYBOARDS: tuple[StoryboardPattern, ...] = (

    # ── 1. Premium Product Hero (4 shots) ───────────────────────────────
    StoryboardPattern(
        pattern_id="premium_product_hero",
        name="Premium Product Hero",
        description=(
            "4-shot cinematic product ad: macro detail → floating product → "
            "lifestyle context → hero CTA. The definitive premium product "
            "storyboard for luxury and tech products."
        ),
        total_shots=4,
        shot_sequence=_mk_shots(
            (1, "macro_detail_shot", "macro_close_up", "soft_rim",
             "slow_dramatic", "3s", "Reveal craftsmanship texture",
             "extreme macro close-up of {product} texture, soft rim light, macro lens, ultra detailed"),
            (2, "floating_product_shot", "floating_object_orbit", "dark_matte",
             "slow_dramatic", "4s", "Show full product in premium context",
             "{product} floating in dark space, slow orbit, dark luxury lighting, minimal composition"),
            (3, "emotional_lifestyle_shot", "handheld", "warm_lifestyle",
             "medium_commercial", "4s", "Show product in aspirational use",
             "lifestyle shot of {product} in use, warm natural light, authentic moment"),
            (4, "hero_shot", "hero_shot", "product_spotlight",
             "slow_dramatic", "3s", "Definitive product beauty shot + CTA",
             "hero shot of {product}, centered, product spotlight, premium commercial, CTA composition"),
        ),
        overall_rhythm="slow_dramatic",
        ideal_for=("luxury watches", "premium electronics", "flagship products", "high-end accessories"),
        estimated_cost=0.7,
        risk_level="low",
    ),

    # ── 2. Quick Social Ad (3 shots) ────────────────────────────────────
    StoryboardPattern(
        pattern_id="quick_social_ad",
        name="Quick Social Ad",
        description=(
            "3-shot rapid social media ad: hook grab → product showcase → CTA. "
            "Optimized for Reels/TikTok. Fast, attention-grabbing, credit-efficient."
        ),
        total_shots=3,
        shot_sequence=_mk_shots(
            (1, "kinetic_montage_shot", "push_in", "neon_accent",
             "fast_kinetic", "2s", "Grab attention instantly",
             "kinetic hook of {product}, neon accent lighting, fast push-in, high energy"),
            (2, "floating_product_shot", "floating_object_orbit", "dark_matte",
             "medium_commercial", "3s", "Showcase product features",
             "{product} floating in dark space, orbit, dark matte lighting, premium tech aesthetic"),
            (3, "hero_shot", "push_in", "product_spotlight",
             "medium_commercial", "2s", "Close with CTA",
             "hero shot of {product}, push-in, product spotlight, CTA, premium commercial"),
        ),
        overall_rhythm="fast_kinetic",
        ideal_for=("social media products", "trending items", "impulse buys", "fashion accessories"),
        estimated_cost=0.4,
        risk_level="low",
    ),

    # ── 3. Cinematic Reveal (5 shots) ───────────────────────────────────
    StoryboardPattern(
        pattern_id="cinematic_reveal_sequence",
        name="Cinematic Reveal Sequence",
        description=(
            "5-shot dramatic reveal: darkness → detail tease → partial reveal → "
            "full reveal → hero ending. Maximum anticipation. For flagship launches."
        ),
        total_shots=5,
        shot_sequence=_mk_shots(
            (1, "cinematic_reveal", "slow_reveal", "low_key_dramatic",
             "slow_dramatic", "3s", "Build mystery and anticipation",
             "product emerging from complete darkness, dramatic lighting tease, anticipation"),
            (2, "macro_detail_shot", "macro_close_up", "soft_rim",
             "slow_dramatic", "3s", "Tease material quality",
             "extreme macro of {product} edge catching light, soft rim light, ultra detailed tease"),
            (3, "cinematic_reveal", "crane_up", "low_key_dramatic",
             "slow_dramatic", "3s", "Partial product reveal",
             "crane up revealing {product} from shadows, dramatic lighting, building anticipation"),
            (4, "luxury_product_shot", "orbit", "dark_matte",
             "slow_dramatic", "4s", "Full product showcase",
             "full orbit around {product} on reflective obsidian, dark luxury lighting, premium craftsmanship"),
            (5, "hero_shot", "dolly_in", "product_spotlight",
             "slow_dramatic", "3s", "Final hero + logo reveal",
             "slow dolly in to {product}, dramatic spotlight, logo reveal composition, premium launch"),
        ),
        overall_rhythm="slow_dramatic",
        ideal_for=("product launches", "flagship releases", "limited editions", "premium brand moments"),
        estimated_cost=1.0,
        risk_level="medium",
    ),

    # ── 4. E-commerce Showcase (4 shots) ────────────────────────────────
    StoryboardPattern(
        pattern_id="ecommerce_showcase",
        name="E-Commerce Showcase",
        description=(
            "4-shot product demonstration for e-commerce: unboxing → detail → "
            "features → lifestyle. Educational and conversion-focused."
        ),
        total_shots=4,
        shot_sequence=_mk_shots(
            (1, "unboxing_shot", "top_down_rotation", "studio_three_point",
             "medium_commercial", "4s", "Satisfying product reveal from packaging",
             "cinematic unboxing of {product}, clean studio lighting, satisfying top-down reveal"),
            (2, "macro_detail_shot", "macro_close_up", "soft_rim",
             "slow_dramatic", "3s", "Show material quality",
             "macro close-up of {product} materials, soft rim light, premium texture detail"),
            (3, "comparison_shot", "cinematic_pan", "studio_three_point",
             "medium_commercial", "3s", "Show features or size context",
             "product demonstration showing {product} features, clean studio lighting, educational"),
            (4, "emotional_lifestyle_shot", "handheld", "natural_window",
             "medium_commercial", "4s", "Show product improving life",
             "lifestyle shot of {product} in beautiful home setting, warm natural light, aspirational"),
        ),
        overall_rhythm="medium_commercial",
        ideal_for=("Amazon products", "home goods", "kitchen gadgets", "everyday carry", "lifestyle products"),
        estimated_cost=0.6,
        risk_level="low",
    ),

    # ── 5. Tech Spec Highlight (4 shots) ────────────────────────────────
    StoryboardPattern(
        pattern_id="tech_spec_highlight",
        name="Tech Spec Highlight",
        description=(
            "4-shot tech product showcase: hero float → detail macro → "
            "feature callout → kinetic energy. Apple-style precision."
        ),
        total_shots=4,
        shot_sequence=_mk_shots(
            (1, "premium_tech_shot", "floating_object_orbit", "dark_matte",
             "medium_commercial", "3s", "Clean floating product intro",
             "{product} floating in dark space, slow orbit, dark matte lighting, premium tech aesthetic"),
            (2, "macro_detail_shot", "macro_close_up", "soft_rim",
             "slow_dramatic", "3s", "Highlight engineering precision",
             "macro close-up of {product} engineering detail, soft rim light, precision craftsmanship"),
            (3, "premium_tech_shot", "push_in", "neon_accent",
             "medium_commercial", "2s", "Feature highlight moment",
             "push-in on {product} key feature, neon accent lighting, tech-forward aesthetic"),
            (4, "kinetic_montage_shot", "tracking_shot", "neon_accent",
             "fast_kinetic", "3s", "Energetic closing with multiple angles",
             "kinetic montage of {product} multiple angles, neon lighting, high energy tech commercial"),
        ),
        overall_rhythm="medium_commercial",
        ideal_for=("gaming gear", "audio equipment", "smart home", "computer accessories"),
        estimated_cost=0.6,
        risk_level="low",
    ),
)


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_storyboards() -> tuple[StoryboardPattern, ...]:
    """Return all storyboard patterns."""
    return _STORYBOARDS


def get_storyboard(pattern_id: str) -> StoryboardPattern | None:
    """Look up a storyboard by ID."""
    for s in _STORYBOARDS:
        if s.pattern_id == pattern_id:
            return s
    return None


def get_storyboards_for_product(product_category: str) -> tuple[StoryboardPattern, ...]:
    """Find storyboards suitable for a product category."""
    cat = product_category.lower()
    result: list[StoryboardPattern] = []
    for s in _STORYBOARDS:
        for ideal in s.ideal_for:
            if cat in ideal.lower():
                result.append(s)
                break
    return tuple(result)


def get_storyboards_by_risk(risk_level: str) -> tuple[StoryboardPattern, ...]:
    """Filter storyboards by risk level."""
    return tuple(s for s in _STORYBOARDS if s.risk_level == risk_level)


def storyboard_count() -> int:
    return len(_STORYBOARDS)

#!/usr/bin/env python3
"""Visual Diversity Engine for advisory creative scoring."""

from __future__ import annotations

from pathlib import Path

from core.creative_intelligence.signal_store import IMPERIO_ROOT, build_creative_signal_state


def _style_pool(state: dict, category: str) -> list[str]:
    catalog = state.get("style_catalog", {}) or {}
    styles = [name for name in catalog.values() if name]
    normalized = []
    for style in styles:
        token = str(style).upper().replace(" ", "_").replace("-", "_")
        if token not in normalized:
            normalized.append(token)
    defaults = [
        "PREMIUM_MINIMAL_STUDIO",
        "DARK_LUXURY_CINEMATIC",
        "WARM_EMOTIONAL_NATURAL",
        "BOLD_HIGH_CONTRAST_IMPACT",
        "CLEAN_WHITE_EDITORIAL",
        "COLORFUL_LIFESTYLE_UGC",
    ]
    for style in defaults:
        if style not in normalized:
            normalized.append(style)
    return normalized


def score_visual_diversity(product_id: str, root: Path = IMPERIO_ROOT, state: dict | None = None) -> dict:
    """
    Score visual repetition for a product/campaign and recommend alternatives.

    Returns advisory output only. It does not mutate campaign memory or prompts.
    """
    state = state or build_creative_signal_state(root=root, persist=False)
    campaigns = state.get("campaigns", []) or []
    campaign = next(
        (c for c in campaigns if product_id in {c.get("campaign_id"), c.get("asin"), c.get("product_name")}),
        None,
    )
    if not campaign:
        return {
            "product_id": product_id,
            "diversity_score": 0.5,
            "recommended_style_variants": _style_pool(state, "general")[:3],
            "repetition_warnings": ["Campaign not found in creative signal state"],
            "platform_notes": _platform_notes(),
        }

    current = campaign.get("primary_mode", "UNKNOWN")
    category = str(campaign.get("category", "general")).lower()
    style_usage = state.get("style_usage", {}) or {}
    repeat_count = int(style_usage.get(current, 0) or 0)
    composition = str((campaign.get("visual_identity", {}) or {}).get("composition", "")).lower()
    same_composition = sum(
        1 for item in campaigns
        if str((item.get("visual_identity", {}) or {}).get("composition", "")).lower() == composition and composition
    )

    penalties = 0.0
    warnings: list[str] = []
    if repeat_count > 1:
        penalties += min(0.45, 0.15 * repeat_count)
        warnings.append(f"Style cooldown: '{current}' appears in {repeat_count} campaigns")
    if same_composition > 1:
        penalties += min(0.25, 0.08 * same_composition)
        warnings.append(f"Composition repeated: '{composition}' appears {same_composition} times")
    if campaign.get("posts_count", 0) >= 5 and campaign.get("performance_score", 100) < 55:
        penalties += 0.2
        warnings.append("Creative fatigue risk: enough posts with weak score")

    pool = [style for style in _style_pool(state, category) if style != current]
    diversity_score = round(max(0.0, min(1.0, 1.0 - penalties)), 3)
    return {
        "product_id": product_id,
        "category": category,
        "current_style": current,
        "diversity_score": diversity_score,
        "recommended_style_variants": pool[:4],
        "repetition_warnings": warnings,
        "platform_notes": _platform_notes(),
    }


def _platform_notes() -> dict[str, dict]:
    return {
        "instagram": {"aspect_ratio": "1:1 or 4:5", "composition": "editorial product hero or carousel story"},
        "tiktok": {"aspect_ratio": "9:16", "composition": "strong hook frame with motion-ready negative space"},
        "pinterest": {"aspect_ratio": "2:3", "composition": "vertical discovery layout, evergreen clarity"},
        "twitter": {"aspect_ratio": "16:9 or 1:1", "composition": "single claim plus product proof"},
        "telegram": {"aspect_ratio": "9:16 or 1:1", "composition": "reviewable carousel with clear product truth"},
    }

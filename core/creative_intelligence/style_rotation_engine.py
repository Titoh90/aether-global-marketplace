#!/usr/bin/env python3
"""
Style Rotation Engine for HERMES Creative Brain v3.

Given a product, its category, past styles used, and performance data,
recommends the next best visual style to avoid repetition.

Core rule: Avoid same style >3 consecutive uses across campaigns.
Style families per category are read from style_director.json and
augmented with universal defaults.

Read-only advisory module. Does not mutate campaign state or prompts.
Can optionally inject style bias into flow_operator.py via feature flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.creative_intelligence.signal_store import IMPERIO_ROOT, build_creative_signal_state

# Universal style families (fallback when no category match)
UNIVERSAL_STYLES: list[str] = [
    "PREMIUM_MINIMAL_STUDIO",
    "DARK_LUXURY_CINEMATIC",
    "WARM_EMOTIONAL_NATURAL",
    "BOLD_HIGH_CONTRAST_IMPACT",
    "CLEAN_WHITE_EDITORIAL",
    "COLORFUL_LIFESTYLE_UGC",
    "TECH_FUTURIST_DARK",
    "SOFT_PASTEL_AESTHETIC",
    "URBAN_STREET_RAW",
    "VINTAGE_FILM_GRAIN",
]

# Category → style mapping (used when style_director.json is unavailable)
CATEGORY_STYLE_FALLBACKS: dict[str, list[str]] = {
    "home": ["PREMIUM_MINIMAL_STUDIO", "WARM_EMOTIONAL_NATURAL", "CLEAN_WHITE_EDITORIAL"],
    "electronics": ["TECH_FUTURIST_DARK", "DARK_LUXURY_CINEMATIC", "PREMIUM_MINIMAL_STUDIO"],
    "beauty": ["SOFT_PASTEL_AESTHETIC", "PREMIUM_MINIMAL_STUDIO", "CLEAN_WHITE_EDITORIAL"],
    "fashion": ["COLORFUL_LIFESTYLE_UGC", "URBAN_STREET_RAW", "CLEAN_WHITE_EDITORIAL"],
    "fitness": ["BOLD_HIGH_CONTRAST_IMPACT", "COLORFUL_LIFESTYLE_UGC", "DARK_LUXURY_CINEMATIC"],
    "kitchen": ["WARM_EMOTIONAL_NATURAL", "CLEAN_WHITE_EDITORIAL", "PREMIUM_MINIMAL_STUDIO"],
    "office": ["CLEAN_WHITE_EDITORIAL", "PREMIUM_MINIMAL_STUDIO", "TECH_FUTURIST_DARK"],
    "outdoor": ["COLORFUL_LIFESTYLE_UGC", "URBAN_STREET_RAW", "WARM_EMOTIONAL_NATURAL"],
    "pet": ["COLORFUL_LIFESTYLE_UGC", "WARM_EMOTIONAL_NATURAL", "SOFT_PASTEL_AESTHETIC"],
    "toy": ["COLORFUL_LIFESTYLE_UGC", "BOLD_HIGH_CONTRAST_IMPACT", "SOFT_PASTEL_AESTHETIC"],
}


@dataclass
class StyleRotationResult:
    """Style recommendation for a product/campaign."""
    product_id: str
    product_name: str
    category: str
    current_style: str
    fatigue_level: str             # "low" | "medium" | "high" | "critical"
    consecutive_uses: int
    recommended_style: str          # primary recommendation
    alternatives: list[str]         # backup recommendations (2-4)
    reason: str                     # human-readable explanation
    avoid_styles: list[str]         # styles to avoid (overused)
    available_styles: int           # total styles in rotation pool


def recommend_style(
    product_id: str,
    root: Path = IMPERIO_ROOT,
    state: dict | None = None,
    force_rotation: bool = False,
) -> StyleRotationResult:
    """
    Recommend the next visual style for a product to avoid repetition.

    Algorithm:
    1. Load campaign and determine current style + usage count
    2. Build rotation pool: category-specific styles + universals
    3. Remove overused styles (>3 campaigns)
    4. Pick best candidate (highest diversity, lowest fatigue)
    5. Fall back to universal default if pool is empty

    Returns advisory StyleRotationResult. Does not mutate anything.
    """
    state = state or build_creative_signal_state(root=root, persist=False)
    campaigns = state.get("campaigns", []) or []
    campaign = next(
        (c for c in campaigns if product_id in {
            c.get("campaign_id"), c.get("asin"), c.get("product_name"),
        }),
        None,
    )

    if not campaign:
        return StyleRotationResult(
            product_id=product_id,
            product_name=product_id,
            category="unknown",
            current_style="UNKNOWN",
            fatigue_level="low",
            consecutive_uses=0,
            recommended_style=UNIVERSAL_STYLES[0],
            alternatives=UNIVERSAL_STYLES[1:4],
            reason="Campaign not found — using default recommendation",
            avoid_styles=[],
            available_styles=len(UNIVERSAL_STYLES),
        )

    current_style = str(campaign.get("primary_mode", "UNKNOWN"))
    category = str(campaign.get("category", "general")).lower()
    style_usage = state.get("style_usage", {}) or {}
    consecutive = int(style_usage.get(current_style, 0) or 0)

    # Build rotation pool
    pool = _build_rotation_pool(state, category, root)
    available = len(pool)

    # Determine fatigue level
    if consecutive >= 4:
        fatigue = "critical"
    elif consecutive >= 3:
        fatigue = "high"
    elif consecutive >= 2:
        fatigue = "medium"
    else:
        fatigue = "low"

    # Identify overused styles (>3 campaigns)
    avoid = [
        style for style, count in style_usage.items()
        if count > 3 and style != current_style
    ][:5]

    # Pick recommendation: exclude current if fatigued, exclude overused
    candidates = [s for s in pool if s != current_style]
    if not force_rotation and fatigue in ("low",) and current_style in pool:
        candidates.insert(0, current_style)  # keep current if low fatigue

    # Re-sort: candidates not in avoid first
    safe = [s for s in candidates if s not in avoid]
    risky = [s for s in candidates if s in avoid]
    ordered = safe + risky

    recommended = ordered[0] if ordered else pool[0]
    alternatives = ordered[1:4] if len(ordered) > 1 else pool[:3]

    # Build reason
    if fatigue == "critical":
        reason = (
            f"CRITICAL rotation needed: '{current_style}' used {consecutive}x. "
            f"Recommended shift to '{recommended}'."
        )
    elif fatigue == "high":
        reason = (
            f"HIGH fatigue: '{current_style}' used {consecutive}x. "
            f"Consider '{recommended}' for diversity."
        )
    elif fatigue == "medium":
        reason = (
            f"Moderate repetition ({consecutive}x). "
            f"'{recommended}' offers stylistic variety."
        )
    else:
        reason = f"Style '{current_style}' is healthy. Alternatively: '{recommended}'."

    return StyleRotationResult(
        product_id=product_id,
        product_name=str(campaign.get("product_name", product_id))[:60],
        category=category,
        current_style=current_style,
        fatigue_level=fatigue,
        consecutive_uses=consecutive,
        recommended_style=recommended,
        alternatives=alternatives,
        reason=reason,
        avoid_styles=avoid,
        available_styles=available,
    )


def recommend_style_for_category(
    category: str,
    root: Path = IMPERIO_ROOT,
    state: dict | None = None,
) -> list[str]:
    """
    Get all recommended styles for a category, ordered by freshness.
    Useful for batch campaign planning.
    """
    state = state or build_creative_signal_state(root=root, persist=False)
    pool = _build_rotation_pool(state, category, root)
    style_usage = state.get("style_usage", {}) or {}

    # Sort by least-used first
    return sorted(pool, key=lambda s: style_usage.get(s, 0))


def _build_rotation_pool(state: dict, category: str, root: Path) -> list[str]:
    """Build ordered rotation pool for a category."""
    pool: list[str] = []

    # 1. Category-specific from style_director.json
    catalog = state.get("style_catalog", {}) or {}
    cat_style = catalog.get(category, "")
    if cat_style and cat_style not in pool:
        pool.append(_normalize_style(cat_style))

    # 2. Category fallbacks
    for style in CATEGORY_STYLE_FALLBACKS.get(category, []):
        if style not in pool:
            pool.append(style)

    # 3. Universal styles
    for style in UNIVERSAL_STYLES:
        if style not in pool:
            pool.append(style)

    return pool


def _normalize_style(style_name: str) -> str:
    """Normalize style name to UPPER_SNAKE_CASE."""
    return str(style_name).upper().replace(" ", "_").replace("-", "_")




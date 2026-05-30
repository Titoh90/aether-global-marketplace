#!/usr/bin/env python3
"""Structured creative hypothesis generator for Hermes Creative Brain v2."""

from __future__ import annotations

from pathlib import Path

from core.creative_intelligence.signal_store import IMPERIO_ROOT, build_creative_signal_state
from core.creative_intelligence.visual_diversity_engine import score_visual_diversity


def generate_creative_brief(product_id: str, root: Path = IMPERIO_ROOT) -> dict:
    """
    Generate a structured creative brief in shadow/advisory mode.

    The output is a hypothesis packet. It never triggers generation, posting, or
    changes to campaign memory.
    """
    state = build_creative_signal_state(root=root, persist=False)
    campaigns = state.get("campaigns", []) or []
    campaign = next(
        (c for c in campaigns if product_id in {c.get("campaign_id"), c.get("asin"), c.get("product_name")}),
        {},
    )
    category = campaign.get("category", "general")
    phase = campaign.get("phase", "EXPLORATION")
    performance = float(campaign.get("performance_score", 50) or 50)
    diversity = score_visual_diversity(product_id, root=root, state=state)
    risks = list(diversity.get("repetition_warnings", []))
    risks.extend(r.get("detail", "") for r in state.get("risk_flags", []) if r.get("product_id") in ("", None, product_id))
    risks = [r for r in risks if r][:6]

    campaign_angle = _campaign_angle(campaign, state)
    return {
        "product_id": product_id,
        "campaign_angle": campaign_angle,
        "visual_style_candidates": diversity.get("recommended_style_variants", [])[:4],
        "hook_variants": _hook_variants(campaign, state),
        "platform_strategy": _platform_strategy(category, campaign_angle, diversity),
        "risk_flags": risks,
        "confidence": _confidence(state, performance, phase, diversity),
    }


def _campaign_angle(campaign: dict, state: dict) -> str:
    if campaign.get("visual_identity", {}).get("mood"):
        return str(campaign["visual_identity"]["mood"])
    hooks = state.get("hook_usage", {}) or {}
    if hooks:
        top = sorted(hooks.items(), key=lambda item: -item[1])[0][0]
        return f"creative divergence around {top}"
    return "exploration: new angle needed"


def _hook_variants(campaign: dict, state: dict) -> list[str]:
    hooks = list(campaign.get("hook_styles", []) or [])
    variants = [f"Refresh {hook} with a sharper first-frame claim" for hook in hooks[:2]]
    defaults = [
        "Contrarian truth: challenge the default buying assumption",
        "Identity mirror: show who the buyer becomes",
        "Specific proof: lead with review, use case, or measurable outcome",
        "Curiosity gap: reveal why this product keeps appearing in routines",
    ]
    for item in defaults:
        if item not in variants:
            variants.append(item)
    return variants[:5]


def _platform_strategy(category: str, campaign_angle: str, diversity: dict) -> dict:
    style = (diversity.get("recommended_style_variants") or ["NEW_STYLE"])[0]
    return {
        "instagram": {"angle": "identity/aspiration", "style": style, "format": "carousel"},
        "tiktok": {"angle": "curiosity/tension", "style": style, "format": "9:16 hook frame"},
        "pinterest": {"angle": "utility/evergreen", "style": style, "format": "2:3 discovery pin"},
        "twitter": {"angle": "opinion/observation", "style": "single proof image", "format": "concise claim"},
        "telegram": {"angle": campaign_angle, "style": "reviewable carousel", "format": "operator preview"},
    }


def _confidence(state: dict, performance: float, phase: str, diversity: dict) -> float:
    source_count = sum(1 for value in (state.get("sources", {}) or {}).values() if value)
    base = min(0.65, 0.08 * source_count)
    perf = min(max(performance, 0), 100) / 100 * 0.2
    div = float(diversity.get("diversity_score", 0.5)) * 0.15
    phase_bonus = 0.05 if phase in ("VALIDATION", "SOFT_LOCK", "HARD_LOCK") else 0.0
    return round(min(1.0, base + perf + div + phase_bonus), 3)

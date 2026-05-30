#!/usr/bin/env python3
"""Read-only proactive digest formatter for Hermes Telegram commands."""

from __future__ import annotations

from pathlib import Path

from core.creative_intelligence.creative_brief_generator import generate_creative_brief
from core.creative_intelligence.signal_store import IMPERIO_ROOT, build_creative_signal_state
from core.creative_intelligence.visual_diversity_engine import score_visual_diversity


def build_proactive_digest(root: Path = IMPERIO_ROOT, topic: str = "creative") -> str:
    state = build_creative_signal_state(root=root, persist=True)
    campaigns = state.get("campaigns", []) or []
    ideas = _ideas(root, campaigns)
    warnings = (state.get("warnings", []) or ["No creative repetition warnings detected"])[:2]
    opportunity = _first_detail(state.get("opportunities", []), "No strong opportunity yet; keep collecting signals")
    risk = _first_detail(state.get("risk_flags", []), "No major creative risk detected")

    lines = [
        "HERMES Creative Brain v2",
        "",
        "3 ideas:",
    ]
    for idx, idea in enumerate(ideas[:3], 1):
        lines.append(f"{idx}. {idea}")
    lines.append("")
    lines.append("2 warnings:")
    for idx, warning in enumerate(warnings[:2], 1):
        lines.append(f"{idx}. {warning}")
    lines.extend([
        "",
        f"1 opportunity: {opportunity}",
        f"1 risk: {risk}",
        "",
        "Mode: read-only advisory. No posting, no execution.",
    ])
    return "\n".join(lines)


def build_brand_report(root: Path = IMPERIO_ROOT) -> str:
    state = build_creative_signal_state(root=root, persist=True)
    brand = state.get("brand", {}) or {}
    warnings = state.get("warnings", []) or []
    opportunities = state.get("opportunities", []) or []
    return "\n".join([
        "HERMES Brand Report",
        f"Visual consistency: {brand.get('visual_consistency_score', 'unknown')}",
        f"Tone consistency: {brand.get('tone_consistency_score', 'unknown')}",
        f"Identity warning: {brand.get('identity_warning', False)}",
        f"Top warning: {warnings[0] if warnings else 'none'}",
        f"Top opportunity: {_first_detail(opportunities, 'none')}",
        "Mode: read-only advisory.",
    ])


def build_why_creative(product_id: str = "", root: Path = IMPERIO_ROOT) -> str:
    state = build_creative_signal_state(root=root, persist=True)
    campaigns = state.get("campaigns", []) or []
    target = product_id or (campaigns[0].get("campaign_id", "") if campaigns else "")
    if not target:
        return "No campaign data available for creative diagnosis."
    diversity = score_visual_diversity(target, root=root, state=state)
    brief = generate_creative_brief(target, root=root)
    return "\n".join([
        f"Creative diagnosis: {target}",
        f"Diversity score: {diversity.get('diversity_score')}",
        f"Current style: {diversity.get('current_style', 'unknown')}",
        f"Recommended styles: {', '.join(diversity.get('recommended_style_variants', [])[:3])}",
        f"Campaign angle: {brief.get('campaign_angle')}",
        f"Risk flags: {len(brief.get('risk_flags', []))}",
        "Mode: read-only advisory.",
    ])


def _ideas(root: Path, campaigns: list[dict]) -> list[str]:
    ideas: list[str] = []
    for campaign in campaigns[:3]:
        product_id = campaign.get("campaign_id", campaign.get("asin", ""))
        brief = generate_creative_brief(product_id, root=root)
        style = (brief.get("visual_style_candidates") or ["new visual style"])[0]
        hook = (brief.get("hook_variants") or ["new hook"])[0]
        ideas.append(f"{campaign.get('product_name', product_id)}: test {style} with {hook}")
    defaults = [
        "Create a product-vs-routine campaign for the strongest active product",
        "Run a Pinterest-style evergreen utility angle for the best visual product",
        "Test one contrarian hook against the current dominant style",
    ]
    for item in defaults:
        if len(ideas) >= 3:
            break
        ideas.append(item)
    return ideas


def _first_detail(items: list, fallback: str) -> str:
    if not items:
        return fallback
    first = items[0]
    if isinstance(first, dict):
        return str(first.get("detail") or first.get("action") or first)
    return str(first)

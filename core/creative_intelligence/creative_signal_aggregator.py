#!/usr/bin/env python3
"""
Creative Signal Aggregator for HERMES Creative Brain v3.

Aggregates signals from all creative intelligence sources:
- Signal store (campaigns, style usage, hooks, risks)
- Visual diversity engine (repetition scoring)
- Creative brief generator (hypothesis packets)
- Competitive intelligence (external trends)

Produces a unified CreativeSignalSnapshot consumed by the proactive brain
and autonomous creative loop.

Read-only advisory module. Zero mutations to production pipeline.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.creative_intelligence.signal_store import (
    IMPERIO_ROOT,
    build_creative_signal_state,
)
from core.creative_intelligence.visual_diversity_engine import score_visual_diversity
from core.creative_intelligence.creative_brief_generator import generate_creative_brief


@dataclass
class ProductCreativeSignal:
    """Per-product creative health snapshot."""
    product_id: str
    product_name: str
    category: str
    phase: str
    current_style: str
    style_fatigue_score: float           # 0-1, higher = more fatigued
    repetition_count: int                # consecutive uses of same style
    diversity_score: float               # from visual_diversity_engine
    performance_score: float
    posts_count: int
    recommended_styles: list[str]        # style rotation candidates
    hook_variants: list[str]
    risk_flags: list[str]
    is_underperforming: bool


@dataclass
class CreativeSignalSnapshot:
    """Unified creative intelligence snapshot for proactive brain."""
    version: int = 3
    generated_at: str = ""
    mode: str = "advisory"

    # Global metrics
    global_style_fatigue: float = 0.0    # average across campaigns
    total_campaigns: int = 0
    campaigns_with_repetition: int = 0
    campaigns_underperforming: int = 0

    # Per-product signals
    product_signals: list[ProductCreativeSignal] = field(default_factory=list)

    # Aggregated style usage
    style_usage: dict[str, int] = field(default_factory=dict)
    most_overused_style: str = ""
    most_overused_count: int = 0

    # Hook usage
    hook_usage: dict[str, int] = field(default_factory=dict)
    most_repeated_hook: str = ""

    # Systemic warnings
    warnings: list[str] = field(default_factory=list)

    # Opportunities from CI / external trends
    opportunities: list[dict] = field(default_factory=list)

    # Risk flags aggregated across all products
    risk_flags: list[dict] = field(default_factory=list)

    # Style catalog metadata
    available_styles: int = 0
    style_families: list[str] = field(default_factory=list)


def aggregate_creative_signals(root: Path = IMPERIO_ROOT, persist: bool = True) -> CreativeSignalSnapshot:
    """
    Build a unified CreativeSignalSnapshot from all CI sources.

    This is the single entry point for the proactive brain and autonomous loop.
    Reads existing production signals. Writes only to
    REVENUE/creative_signal_snapshot.json (if persist=True).
    """
    root = Path(root)
    state = build_creative_signal_state(root=root, persist=False)
    campaigns = state.get("campaigns", []) or []

    snapshot = CreativeSignalSnapshot(
        version=3,
        generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        mode="advisory",
        total_campaigns=len(campaigns),
        style_usage=state.get("style_usage", {}),
        hook_usage=state.get("hook_usage", {}),
        warnings=list(state.get("warnings", []) or []),
        opportunities=list(state.get("opportunities", []) or []),
        risk_flags=list(state.get("risk_flags", []) or []),
        style_families=list((state.get("style_catalog") or {}).values()),
        available_styles=len(state.get("style_catalog", {}) or {}),
    )

    # Per-product signals
    fatigue_sum = 0.0
    for campaign in campaigns:
        product_id = campaign.get("campaign_id", campaign.get("asin", ""))
        diversity = score_visual_diversity(product_id, root=root, state=state)
        brief = generate_creative_brief(product_id, root=root)

        current_style = campaign.get("primary_mode", "UNKNOWN")
        style_count = snapshot.style_usage.get(current_style, 0)
        repetition = max(0, style_count - 1)  # -1 because current campaign counts itself
        fatigue = min(1.0, repetition * 0.25)
        perf = float(campaign.get("performance_score", 50) or 50)
        is_weak = perf < 55 and campaign.get("posts_count", 0) >= 3

        ps = ProductCreativeSignal(
            product_id=product_id,
            product_name=str(campaign.get("product_name", product_id))[:60],
            category=str(campaign.get("category", "general")),
            phase=str(campaign.get("phase", "EXPLORATION")),
            current_style=current_style,
            style_fatigue_score=round(fatigue, 3),
            repetition_count=repetition,
            diversity_score=diversity.get("diversity_score", 0.5),
            performance_score=perf,
            posts_count=int(campaign.get("posts_count", 0) or 0),
            recommended_styles=list(diversity.get("recommended_style_variants", []) or [])[:4],
            hook_variants=list(brief.get("hook_variants", []) or [])[:5],
            risk_flags=list(diversity.get("repetition_warnings", []) or []),
            is_underperforming=is_weak,
        )
        snapshot.product_signals.append(ps)
        fatigue_sum += fatigue
        if repetition > 0:
            snapshot.campaigns_with_repetition += 1
        if is_weak:
            snapshot.campaigns_underperforming += 1

    # Global fatigue
    snapshot.global_style_fatigue = round(
        fatigue_sum / len(campaigns) if campaigns else 0.0, 3
    )

    # Most overused style
    if snapshot.style_usage:
        top_style = max(snapshot.style_usage.items(), key=lambda x: x[1])
        snapshot.most_overused_style = top_style[0]
        snapshot.most_overused_count = top_style[1]

    # Most repeated hook
    if snapshot.hook_usage:
        top_hook = max(snapshot.hook_usage.items(), key=lambda x: x[1])
        snapshot.most_repeated_hook = top_hook[0]

    # Add systemic warnings
    if snapshot.campaigns_with_repetition > 0:
        snapshot.warnings.append(
            f"{snapshot.campaigns_with_repetition}/{snapshot.total_campaigns} "
            f"campaigns show style repetition"
        )
    if snapshot.campaigns_underperforming > 0:
        snapshot.warnings.append(
            f"{snapshot.campaigns_underperforming} campaigns underperforming "
            f"(score < 55 with ≥3 posts)"
        )
    if snapshot.global_style_fatigue > 0.4:
        snapshot.warnings.append(
            f"Global style fatigue high ({snapshot.global_style_fatigue:.2f})"
        )
    if snapshot.most_overused_count > 1:
        snapshot.warnings.append(
            f"Style '{snapshot.most_overused_style}' overused "
            f"({snapshot.most_overused_count} campaigns)"
        )

    if persist:
        out = root / "REVENUE" / "creative_signal_snapshot.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(_snapshot_to_dict(snapshot), indent=2, default=str))

    return snapshot


def _snapshot_to_dict(s: CreativeSignalSnapshot) -> dict[str, Any]:
    return {
        "version": s.version,
        "generated_at": s.generated_at,
        "mode": s.mode,
        "global_style_fatigue": s.global_style_fatigue,
        "total_campaigns": s.total_campaigns,
        "campaigns_with_repetition": s.campaigns_with_repetition,
        "campaigns_underperforming": s.campaigns_underperforming,
        "style_usage": s.style_usage,
        "most_overused_style": s.most_overused_style,
        "most_overused_count": s.most_overused_count,
        "hook_usage": s.hook_usage,
        "most_repeated_hook": s.most_repeated_hook,
        "warnings": s.warnings,
        "opportunities": s.opportunities,
        "risk_flags": s.risk_flags,
        "available_styles": s.available_styles,
        "style_families": s.style_families,
        "product_signals": [
            {
                "product_id": ps.product_id,
                "product_name": ps.product_name,
                "category": ps.category,
                "phase": ps.phase,
                "current_style": ps.current_style,
                "style_fatigue_score": ps.style_fatigue_score,
                "repetition_count": ps.repetition_count,
                "diversity_score": ps.diversity_score,
                "performance_score": ps.performance_score,
                "posts_count": ps.posts_count,
                "recommended_styles": ps.recommended_styles,
                "hook_variants": ps.hook_variants,
                "risk_flags": ps.risk_flags,
                "is_underperforming": ps.is_underperforming,
            }
            for ps in s.product_signals
        ],
    }

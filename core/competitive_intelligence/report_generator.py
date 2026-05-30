#!/usr/bin/env python3
"""
report_generator.py — Generates structured intelligence reports.

Produces IntelligenceReport with:
- Ranked trends
- Global insights
- Archetype engine feed recommendations

Usage:
    from core.competitive_intelligence.report_generator import generate_report

    report = generate_report(trends, insights)
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.competitive_intelligence.schemas import (
    CompetitorInsight, TrendRank, IntelligenceReport,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _generate_global_insights(
    trends:   list[TrendRank],
    insights: list[CompetitorInsight],
) -> tuple[str, ...]:
    """Generate human-readable global insights across all competitors."""
    items: list[str] = []

    if not trends:
        return ("No competitor data available.",)

    # Top performer
    top = trends[0]
    items.append(
        f"Top performer: @{top.account} ({top.style}) — "
        f"engagement {top.engagement_rate:.1%}, viral score {top.viral_score:.2f}"
    )

    # Style dominance
    style_counts: dict[str, int] = {}
    for t in trends:
        style_counts[t.style] = style_counts.get(t.style, 0) + 1
    dom_style = max(style_counts, key=lambda k: style_counts[k]) if style_counts else "unknown"
    dom_count = style_counts.get(dom_style, 0)
    total = max(len(trends), 1)
    items.append(
        f"Dominant visual style: {dom_style.replace('_', ' ')} "
        f"({dom_count}/{total} accounts, {dom_count/total:.0%})"
    )

    # Hook patterns
    all_patterns: list[str] = []
    for t in trends:
        all_patterns.extend(t.patterns)
    if all_patterns:
        # Most common pattern
        pattern_counts: dict[str, int] = {}
        for p in all_patterns:
            pattern_counts[p] = pattern_counts.get(p, 0) + 1
        top_pattern = max(pattern_counts, key=lambda k: pattern_counts[k])
        items.append(f"Most common pattern: {top_pattern}")

    # Engagement range
    rates = [t.engagement_rate for t in trends if t.engagement_rate > 0]
    if rates:
        items.append(
            f"Engagement range: {min(rates):.1%}–{max(rates):.1%} "
            f"(avg {sum(rates)/len(rates):.1%})"
        )

    # Actionable insight
    if dom_style != "unknown":
        items.append(
            f"RECOMMENDATION: Test {dom_style.replace('_', ' ')} style "
            f"in Visual Intelligence pipeline."
        )

    return tuple(items)


def _generate_archetype_feeds(insights: list[CompetitorInsight]) -> tuple[str, ...]:
    """Generate archetype engine feed tags."""
    tags: set[str] = set()
    for insight in insights:
        for tag in insight.recommended_archetype_tags:
            tags.add(tag)
    return tuple(sorted(tags))


# ── Public API ────────────────────────────────────────────────────────────────

def generate_report(
    trends:   list[TrendRank],
    insights: list[CompetitorInsight],
) -> IntelligenceReport:
    """
    Generate a complete competitive intelligence report.

    Args:
        trends:   ranked trends from trend_ranker
        insights: all competitor insights from insight_engine

    Returns:
        IntelligenceReport with trends, global insights, and archetype feeds.
    """
    global_insights = _generate_global_insights(trends, insights)
    archetype_feeds = _generate_archetype_feeds(insights)

    return IntelligenceReport(
        generated_at=_now_iso(),
        accounts_analyzed=len(insights),
        trends=tuple(trends),
        global_insights=global_insights,
        archetype_feeds=archetype_feeds,
    )

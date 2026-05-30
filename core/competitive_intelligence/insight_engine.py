#!/usr/bin/env python3
"""
insight_engine.py — Aggregates competitor fingerprints into actionable insights.

Processes PublicPostFingerprints → CompetitorInsight per account.
Feeds Visual Intelligence and Archetype Engine with pattern recommendations.

Usage:
    from core.competitive_intelligence.insight_engine import build_insights

    insights = build_insights(account, fingerprints)
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.competitive_intelligence.schemas import (
    CompetitorAccount, PublicPostFingerprint, CompetitorInsight,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _compute_frequency(posts_per_week_est: float) -> str:
    """Map estimated posts per week to frequency label."""
    if posts_per_week_est >= 14:
        return "multi_daily"
    if posts_per_week_est >= 7:
        return "daily"
    if posts_per_week_est >= 3:
        return "weekly_few"
    if posts_per_week_est >= 1:
        return "weekly"
    if posts_per_week_est >= 0.2:
        return "sparse"
    return "irregular"


def _distribution(counts: dict[str, int], total: int) -> dict[str, float]:
    """Convert counts to proportional distribution."""
    if total == 0:
        return {}
    return {k: round(v / total, 4) for k, v in counts.items()}


def _dominant(counts: dict[str, int]) -> str:
    """Return the key with highest count."""
    if not counts:
        return "unknown"
    return max(counts, key=lambda k: counts[k])


def _generate_top_patterns(
    visual_styles: dict[str, int],
    hook_types:    dict[str, int],
    cta_types:     dict[str, int],
    total:         int,
) -> tuple[str, ...]:
    """Generate human-readable top patterns."""
    patterns: list[str] = []
    dom_style = _dominant(visual_styles)
    dom_hook = _dominant(hook_types)
    dom_cta = _dominant(cta_types)

    if dom_style != "unknown":
        patterns.append(f"{dom_style.replace('_', ' ')} aesthetic")

    if dom_hook != "unknown":
        readable_hook = dom_hook.replace("_", " ")
        patterns.append(f"{readable_hook} opening")

    if dom_cta not in ("none", "unknown"):
        readable_cta = dom_cta.replace("_", " ")
        patterns.append(f"{readable_cta} CTA")

    # Add frequency-based patterns
    style_count = sum(1 for s in visual_styles if s != "unknown")
    if style_count >= 3:
        patterns.append("multi-style strategy")

    hook_count = sum(1 for h in hook_types if h != "unknown")
    if hook_count >= 3:
        patterns.append("diverse hook approach")

    return tuple(patterns[:5])


def _recommend_archetype_tags(
    dom_style: str,
    dom_hook:  str,
    dom_cta:   str,
) -> tuple[str, ...]:
    """Generate recommended archetype tags for Visual Intelligence."""
    tags: list[str] = []

    if dom_style != "unknown":
        tags.append(dom_style)
    if dom_hook != "unknown":
        tags.append(dom_hook)
    if dom_cta not in ("none", "unknown"):
        tags.append(f"cta_{dom_cta}")

    return tuple(tags)


# ── Public API ────────────────────────────────────────────────────────────────

def build_insights(
    account:       CompetitorAccount,
    fingerprints:  list[PublicPostFingerprint],
    posts_per_week_est: float = 0.0,
) -> CompetitorInsight:
    """
    Aggregate PublicPostFingerprints into a single CompetitorInsight.

    Args:
        account:             competitor account
        fingerprints:        list of post fingerprints (from public_scraper)
        posts_per_week_est:  estimated posting frequency

    Returns:
        CompetitorInsight — never raises. May have default/zero values if no data.
    """
    total = len(fingerprints)
    freq_label = _compute_frequency(posts_per_week_est)
    if total == 0:
        return CompetitorInsight(
            account_id=account.account_id,
            username=account.username,
            platform=account.platform,
            analyzed_at=_now_iso(),
            avg_engagement_rate=0.0,
            estimated_posts_per_week=round(posts_per_week_est, 2),
            frequency_label=freq_label,
            dominant_style="unknown",
            style_distribution={},
            dominant_hook="unknown",
            hook_distribution={},
            dominant_cta="none",
            cta_distribution={},
            viral_score=0.0,
            top_patterns=(),
            recommended_archetype_tags=(),
        )

    # Aggregate metrics
    total_engagement = sum(f.engagement_rate for f in fingerprints)
    avg_engagement = total_engagement / total

    # Count distributions
    style_counts: dict[str, int] = {}
    hook_counts: dict[str, int] = {}
    cta_counts: dict[str, int] = {}

    for fp in fingerprints:
        style_counts[fp.visual_style] = style_counts.get(fp.visual_style, 0) + 1
        hook_counts[fp.hook_type] = hook_counts.get(fp.hook_type, 0) + 1
        cta_counts[fp.cta_type] = cta_counts.get(fp.cta_type, 0) + 1

    dom_style = _dominant(style_counts)
    dom_hook = _dominant(hook_counts)
    dom_cta = _dominant(cta_counts)

    # Build distributions
    style_dist = _distribution(style_counts, total)
    hook_dist = _distribution(hook_counts, total)
    cta_dist = _distribution(cta_counts, total)

    # Generate patterns and archetype tags
    top_patterns = _generate_top_patterns(style_counts, hook_counts, cta_counts, total)
    archetype_tags = _recommend_archetype_tags(dom_style, dom_hook, dom_cta)

    return CompetitorInsight(
        account_id=account.account_id,
        username=account.username,
        platform=account.platform,
        analyzed_at=_now_iso(),
        avg_engagement_rate=round(avg_engagement, 6),
        estimated_posts_per_week=round(posts_per_week_est, 2),
        frequency_label=freq_label,
        dominant_style=dom_style,
        style_distribution=style_dist,
        dominant_hook=dom_hook,
        hook_distribution=hook_dist,
        dominant_cta=dom_cta,
        cta_distribution=cta_dist,
        viral_score=0.0,  # computed later by trend_ranker
        top_patterns=top_patterns,
        recommended_archetype_tags=archetype_tags,
    )


def build_all_insights(
    accounts_and_fingerprints: list[tuple[CompetitorAccount, list[PublicPostFingerprint], float]],
) -> list[CompetitorInsight]:
    """
    Build insights for multiple accounts in batch.

    Args:
        accounts_and_fingerprints: list of (account, fingerprints, posts_per_week_est) tuples

    Returns:
        List of CompetitorInsight — same order as input.
    """
    return [
        build_insights(account, fingerprints, freq)
        for account, fingerprints, freq in accounts_and_fingerprints
    ]

#!/usr/bin/env python3
"""
trend_ranker.py — Scores and ranks competitor accounts by viral signals.

Computes:
- Viral score (0.0–1.0): composite of engagement + frequency + style distinctiveness
- Trend ranking: ordered by viral_score descending

Usage:
    from core.competitive_intelligence.trend_ranker import rank_trends

    trends = rank_trends([insight1, insight2, ...])
"""

from __future__ import annotations

import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.competitive_intelligence.schemas import CompetitorInsight, TrendRank

# ── Scoring weights ──────────────────────────────────────────────────────────

_WEIGHT_ENGAGEMENT   = 0.40
_WEIGHT_FREQUENCY    = 0.25
_WEIGHT_STYLE        = 0.20
_WEIGHT_HOOK_VARIETY = 0.15

# Frequency score mapping (higher frequency → higher score, caps at multi_daily)
_FREQUENCY_SCORES: dict[str, float] = {
    "multi_daily": 1.0,
    "daily":       0.85,
    "weekly_few":  0.60,
    "weekly":      0.40,
    "sparse":      0.15,
    "irregular":   0.10,
}

# Style distinctiveness: more unique styles score higher (fewer competitors using same style)
_MIN_STYLE_SCORE = 0.3


# ── Helpers ───────────────────────────────────────────────────────────────────

def _score_engagement(rate: float) -> float:
    """
    Score engagement rate on 0.0–1.0 scale.
    Above 5% = 1.0, 0% = 0.0, linear in between.
    """
    return min(rate / 0.05, 1.0)


def _score_frequency(label: str) -> float:
    """Score posting frequency."""
    return _FREQUENCY_SCORES.get(label, 0.1)


def _score_style_distinctiveness(
    dominant_style: str,
    all_insights:  list[CompetitorInsight],
) -> float:
    """More unique style = higher score. Common style = lower score."""
    same_style = sum(1 for i in all_insights if i.dominant_style == dominant_style)
    total = max(len(all_insights), 1)
    commonality = same_style / total
    # Invert: 1 competitor using style = 1.0, everyone using it = 0.3
    return 1.0 - (commonality * 0.7)


def _score_hook_variety(insight: CompetitorInsight) -> float:
    """More hook types used = higher score."""
    hook_types_used = len(insight.hook_distribution)
    return min(hook_types_used / 5.0, 1.0)  # 5+ hook types = perfect score


def _compute_viral_score(
    insight:       CompetitorInsight,
    all_insights:  list[CompetitorInsight],
) -> float:
    """Compute composite viral score."""
    eng_score  = _score_engagement(insight.avg_engagement_rate)
    freq_score = _score_frequency(insight.frequency_label)
    style_score = _score_style_distinctiveness(insight.dominant_style, all_insights)
    hook_score = _score_hook_variety(insight)

    return round(
        eng_score  * _WEIGHT_ENGAGEMENT +
        freq_score * _WEIGHT_FREQUENCY +
        style_score * _WEIGHT_STYLE +
        hook_score * _WEIGHT_HOOK_VARIETY,
        4,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def rank_trends(
    insights: list[CompetitorInsight],
) -> list[TrendRank]:
    """
    Rank competitor insights by viral score, descending.

    Args:
        insights: list of CompetitorInsight from insight_engine

    Returns:
        List of TrendRank — sorted by viral_score (highest first).
        Empty list if no insights.
    """
    if not insights:
        return []

    results: list[tuple[float, CompetitorInsight]] = []
    for insight in insights:
        score = _compute_viral_score(insight, insights)
        results.append((score, insight))

    # Sort by score descending, then by engagement rate descending for ties
    results.sort(key=lambda x: (x[0], x[1].avg_engagement_rate), reverse=True)

    return [
        TrendRank(
            account=insight.username,
            style=insight.dominant_style,
            engagement_rate=round(insight.avg_engagement_rate, 4),
            viral_score=score,
            patterns=insight.top_patterns,
        )
        for score, insight in results
    ]

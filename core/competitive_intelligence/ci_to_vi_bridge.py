#!/usr/bin/env python3
"""
ci_to_vi_bridge.py — Feeds Competitive Intelligence insights into Visual Intelligence.

Converts CompetitorInsight objects → archetype_memory.upsert_archetype() calls.
This is the read-only-to-read path: CI analyzes public data, VI learns from patterns.

Rules:
- NEVER modifies the core pipeline, revenue layer, or dispatch gate
- NEVER stores competitor content — only style labels and metrics
- Non-blocking — failures logged, never raised
- All AI calls through dispatch() only

Usage:
    from core.competitive_intelligence.ci_to_vi_bridge import feed_insights_to_vi

    result = feed_insights_to_vi(insights)
"""

from __future__ import annotations

import datetime
import hashlib
import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.competitive_intelligence.schemas import CompetitorInsight, VISUAL_STYLES


# ── Style mapping: CI visual_styles → VI archetype_memory labels ──────────────

_CI_STYLE_TO_VI_LABEL: dict[str, str] = {
    "luxury_dark":          "DARK_LUXURY_CINEMATIC",
    "minimal_clean":        "PREMIUM_MINIMAL_STUDIO",
    "warm_lifestyle":       "WARM_EMOTIONAL_NATURAL",
    "cinematic_commercial": "DARK_LUXURY_CINEMATIC",
    "tech_premium":         "PREMIUM_MINIMAL_STUDIO",
    "unknown":              "",
}


def _make_archetype_name(insight: CompetitorInsight) -> str:
    """Generate a stable archetype name from CI insight data."""
    raw = f"CI_{insight.platform}_{insight.dominant_style}_{insight.dominant_hook}"
    short_hash = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return f"CI_{insight.dominant_style}_{short_hash}"


def _make_dummy_centroid(dim: int = 384, seed: int | None = None) -> "np.ndarray":
    """
    Create a deterministic dummy centroid from CI data.
    Since CI doesn't have image embeddings, we use a hash-based vector
    as a placeholder. This allows upsert_archetype to work without errors.
    The centroid is NOT used for similarity search — only as a placeholder.

    Args:
        dim:  embedding dimension (default 384)
        seed: random seed — use None for fixed seed, or pass an int for variety
    """
    import numpy as np
    effective_seed = 42 if seed is None else seed
    rng = np.random.default_rng(effective_seed)
    centroid = rng.normal(0, 0.1, size=(dim,)).astype(np.float32)
    centroid = centroid / (np.linalg.norm(centroid) + 1e-8)
    return centroid


def _insight_similarity_score(insight: CompetitorInsight) -> float:
    """
    Compute a similarity proxy from engagement rate and data volume.
    Higher engagement + more data → higher similarity proxy.
    Capped at 0.95.
    """
    base = min(insight.avg_engagement_rate * 10, 0.7)  # engagement weighted
    bonus = (
        len(insight.style_distribution) * 0.03 +
        len(insight.hook_distribution) * 0.02 +
        len(insight.cta_distribution) * 0.02
    )
    return round(min(base + bonus, 0.95), 6)


def _insight_revenue_proxy(insight: CompetitorInsight) -> float:
    """
    CI doesn't have real revenue data (read-only public analysis).
    Use engagement rate as a revenue signal proxy.
    High engagement rate → potential for high revenue.
    """
    return round(min(insight.avg_engagement_rate * 5, 1.0), 6)


# ── Public API ────────────────────────────────────────────────────────────────

def feed_insights_to_vi(
    insights: list[CompetitorInsight],
    category: str = "competitive_intelligence",
) -> dict:
    """
    Feed Competitive Intelligence insights into Visual Intelligence archetype_memory.

    Each CompetitorInsight becomes one archetype in the category-scoped memory.
    The VI system can then use these for prompt bias recommendations.

    Args:
        insights: list of CompetitorInsight from insight_engine
        category: VI category to store under (default: "competitive_intelligence")

    Returns:
        {"fed": int, "skipped": int, "errors": int, "category": str}
        Never raises.
    """
    fed = 0
    skipped = 0
    errors = 0

    try:
        from core.visual_intelligence.archetype_memory import upsert_archetype
    except ImportError as e:
        return {
            "fed": 0, "skipped": 0, "errors": len(insights),
            "category": category,
            "error_detail": f"archetype_memory not available: {e}",
        }

    for insight in insights:
        try:
            # Skip unknown/empty styles
            if insight.dominant_style == "unknown" or not insight.recommended_archetype_tags:
                skipped += 1
                continue

            # Map CI visual style to VI archetype label
            vi_style = _CI_STYLE_TO_VI_LABEL.get(insight.dominant_style, "")
            if not vi_style:
                skipped += 1
                continue

            # Build style labels: VI style + CI recommended tags
            style_labels = [vi_style] + [
                tag.replace("_", " ").title()
                for tag in insight.recommended_archetype_tags
                if not tag.startswith("cta_")
            ]

            # Deduplicate
            style_labels = list(dict.fromkeys(style_labels))

            archetype_name = _make_archetype_name(insight)
            similarity = _insight_similarity_score(insight)
            revenue = _insight_revenue_proxy(insight)
            centroid = _make_dummy_centroid(seed=hash(archetype_name) % (2**31))

            upsert_archetype(
                category=category,
                name=archetype_name,
                style_labels=style_labels,
                centroid=centroid,
                revenue=revenue,
                similarity=similarity,
            )

            fed += 1

        except Exception as e:
            print(f"[ci_to_vi_bridge] WARNING: failed to feed insight {insight.username}: {e}")
            errors += 1

    return {
        "fed":      fed,
        "skipped":  skipped,
        "errors":   errors,
        "category": category,
    }


def feed_report_to_vi(
    trends: list,
    insights: list[CompetitorInsight],
    category: str = "competitive_intelligence",
) -> dict:
    """
    Feed a full IntelligenceReport's insights to VI archetype_memory.
    Convenience wrapper around feed_insights_to_vi().

    Returns same shape as feed_insights_to_vi().
    """
    return feed_insights_to_vi(insights, category=category)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    # Example: read insights from a file and feed them
    import argparse
    ap = argparse.ArgumentParser(description="Feed CI insights into VI archetype memory")
    ap.add_argument("--insights-json", metavar="PATH", help="JSON file with list of CompetitorInsight dicts")
    ap.add_argument("--category", default="competitive_intelligence", help="VI category")
    args = ap.parse_args()

    if args.insights_json:
        data = json.loads(Path(args.insights_json).read_text())
        # Reconstruct CompetitorInsight objects from dicts
        insights = []
        for d in data:
            try:
                insight = CompetitorInsight(
                    account_id=d.get("account_id", ""),
                    username=d.get("username", ""),
                    platform=d.get("platform", ""),
                    analyzed_at=d.get("analyzed_at", ""),
                    avg_engagement_rate=float(d.get("avg_engagement_rate", 0)),
                    estimated_posts_per_week=float(d.get("estimated_posts_per_week", 0)),
                    frequency_label=d.get("frequency_label", "irregular"),
                    dominant_style=d.get("dominant_style", "unknown"),
                    style_distribution=d.get("style_distribution", {}),
                    dominant_hook=d.get("dominant_hook", "unknown"),
                    hook_distribution=d.get("hook_distribution", {}),
                    dominant_cta=d.get("dominant_cta", "none"),
                    cta_distribution=d.get("cta_distribution", {}),
                    viral_score=float(d.get("viral_score", 0)),
                    top_patterns=tuple(d.get("top_patterns", [])),
                    recommended_archetype_tags=tuple(d.get("recommended_archetype_tags", [])),
                )
                insights.append(insight)
            except Exception as e:
                print(f"  [ci_to_vi_bridge] skip malformed insight: {e}")

        if insights:
            result = feed_insights_to_vi(insights, category=args.category)
            print(json.dumps(result, indent=2))
        else:
            print("  No valid insights to feed.")

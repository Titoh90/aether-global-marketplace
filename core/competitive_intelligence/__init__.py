#!/usr/bin/env python3
"""
core/competitive_intelligence — Competitive Intelligence Layer (Phase 2).

READ-ONLY system that analyzes public competitor data to extract:
  - Visual styles (luxury_dark, minimal_clean, warm_lifestyle, etc.)
  - Engagement patterns
  - Hook structures (question_led, storytelling, curiosity_gap, etc.)
  - Posting frequency
  - Viral signals
  - Product positioning

CRITICAL RULES:
  - ONLY analyzes public data
  - NEVER copies raw content
  - ONLY extracts patterns
  - NEVER interacts with users
  - NEVER posts content automatically
  - NEVER does aggressive scraping
  - NEVER modifies core system

Feeds:
  - Visual Intelligence pipeline (archetype tags)
  - Archetype Engine (visual style + hook recommendations)

Public API:
    from core.competitive_intelligence.competitor_registry import (
        add_competitor, get_active_competitors, get_by_platform, remove_competitor
    )
    from core.competitive_intelligence.public_scraper import (
        fingerprint_account, fingerprint_raw_post
    )
    from core.competitive_intelligence.visual_pattern_extractor import (
        classify_visual_style, classify_batch
    )
    from core.competitive_intelligence.caption_analyzer import (
        analyze_caption, analyze_batch, summarize_patterns
    )
    from core.competitive_intelligence.insight_engine import (
        build_insights, build_all_insights
    )
    from core.competitive_intelligence.trend_ranker import rank_trends
    from core.competitive_intelligence.report_generator import generate_report
    from core.competitive_intelligence.ci_to_vi_bridge import (
        feed_insights_to_vi, feed_report_to_vi
    )
    from core.competitive_intelligence.ci_scheduler import (
        run_ci_pipeline, run_background_loop
    )
"""

from core.competitive_intelligence.schemas import (
    CompetitorAccount,
    PublicPostFingerprint,
    CompetitorInsight,
    TrendRank,
    IntelligenceReport,
    VISUAL_STYLES,
    HOOK_TYPES,
    CTA_TYPES,
    FREQUENCY_LABELS,
)
from core.competitive_intelligence.competitor_registry import (
    add_competitor,
    remove_competitor,
    get_active_competitors,
    get_by_platform,
)
from core.competitive_intelligence.public_scraper import (
    fingerprint_account,
    fingerprint_raw_post,
)
from core.competitive_intelligence.visual_pattern_extractor import (
    classify_visual_style,
)
from core.competitive_intelligence.caption_analyzer import (
    analyze_caption,
    summarize_patterns,
)
from core.competitive_intelligence.insight_engine import (
    build_insights,
)
from core.competitive_intelligence.trend_ranker import rank_trends
from core.competitive_intelligence.report_generator import generate_report
from core.competitive_intelligence.ci_to_vi_bridge import (
    feed_insights_to_vi,
    feed_report_to_vi,
)
from core.competitive_intelligence.ci_scheduler import (
    run_ci_pipeline,
    run_background_loop,
)

__all__ = [
    # Schemas
    "CompetitorAccount",
    "PublicPostFingerprint",
    "CompetitorInsight",
    "TrendRank",
    "IntelligenceReport",
    "VISUAL_STYLES",
    "HOOK_TYPES",
    "CTA_TYPES",
    "FREQUENCY_LABELS",
    # Registry
    "add_competitor",
    "remove_competitor",
    "get_active_competitors",
    "get_by_platform",
    # Scraper
    "fingerprint_account",
    "fingerprint_raw_post",
    # Visual
    "classify_visual_style",
    # Caption
    "analyze_caption",
    "summarize_patterns",
    # Engine
    "build_insights",
    "rank_trends",
    "generate_report",
    # Bridge to Visual Intelligence
    "feed_insights_to_vi",
    "feed_report_to_vi",
    # Scheduler
    "run_ci_pipeline",
    "run_background_loop",
]

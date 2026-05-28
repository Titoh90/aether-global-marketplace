#!/usr/bin/env python3
"""
test_competitive_intelligence.py — Tests for core/competitive_intelligence/

Coverage:
- Schemas: frozen dataclasses, VISUAL_STYLES, HOOK_TYPES, CTA_TYPES
- Competitor registry: add, dedup, remove, get by platform/niche
- Public scraper: fingerprint_raw_post, rate limiting, pattern extraction
- Visual pattern extractor: style classification, palette/composition inference
- Caption analyzer: hook/CTA detection, structural features, batch summarization
- Insight engine: build_insights, distributions, pattern generation
- Trend ranker: viral scoring, ranking, empty input
- Report generator: report structure, global insights
- Integration: full pipeline, isolation checks
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_IMPERIO_ROOT = Path(__file__).parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))


# ═══════════════════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchemas:
    def test_competitor_account_frozen(self):
        from core.competitive_intelligence.schemas import CompetitorAccount
        account = CompetitorAccount(account_id="acc1", username="@brand", platform="instagram", niche="tech")
        with pytest.raises((AttributeError, TypeError)):
            account.username = "mutated"

    def test_public_post_fingerprint_frozen(self):
        from core.competitive_intelligence.schemas import PublicPostFingerprint
        fp = PublicPostFingerprint(
            fingerprint_id="fp1", account_id="acc1", platform="ig",
            collected_at="ts", hook_type="hook_first", cta_type="none",
            sentence_count=3, avg_sentence_length=12.0, has_emoji=True,
            emoji_count=2, has_hashtags=False, hashtag_count=0, has_question=False,
            visual_style="tech_premium", color_palette="cool_tones",
            composition="center_product", text_overlay=True,
        )
        with pytest.raises((AttributeError, TypeError)):
            fp.visual_style = "mutated"

    def test_competitor_insight_frozen(self):
        from core.competitive_intelligence.schemas import CompetitorInsight
        insight = CompetitorInsight(
            account_id="a1", username="@b", platform="ig", analyzed_at="ts",
            avg_engagement_rate=0.05, estimated_posts_per_week=3.0,
            frequency_label="weekly_few", dominant_style="minimal_clean",
            style_distribution={}, dominant_hook="hook_first",
            hook_distribution={}, dominant_cta="link_in_bio",
            cta_distribution={}, viral_score=0.7,
            top_patterns=(), recommended_archetype_tags=(),
        )
        with pytest.raises((AttributeError, TypeError)):
            insight.viral_score = 0.9

    def test_trend_rank_frozen(self):
        from core.competitive_intelligence.schemas import TrendRank
        rank = TrendRank(account="@a", style="luxury_dark", engagement_rate=0.05, viral_score=0.8, patterns=("hook-first",))
        with pytest.raises((AttributeError, TypeError)):
            rank.viral_score = 0.1

    def test_intelligence_report_frozen(self):
        from core.competitive_intelligence.schemas import IntelligenceReport, TrendRank
        rank = TrendRank(account="@a", style="minimal_clean", engagement_rate=0.03, viral_score=0.6, patterns=())
        report = IntelligenceReport(generated_at="ts", accounts_analyzed=1, trends=(rank,), global_insights=(), archetype_feeds=())
        with pytest.raises((AttributeError, TypeError)):
            report.accounts_analyzed = 99

    def test_visual_styles_frozenset(self):
        from core.competitive_intelligence.schemas import VISUAL_STYLES
        assert isinstance(VISUAL_STYLES, frozenset)
        assert "luxury_dark" in VISUAL_STYLES
        assert "tech_premium" in VISUAL_STYLES

    def test_hook_types_frozenset(self):
        from core.competitive_intelligence.schemas import HOOK_TYPES
        assert isinstance(HOOK_TYPES, frozenset)
        assert "hook_first" in HOOK_TYPES
        assert "question_led" in HOOK_TYPES

    def test_cta_types_frozenset(self):
        from core.competitive_intelligence.schemas import CTA_TYPES
        assert isinstance(CTA_TYPES, frozenset)
        assert "link_in_bio" in CTA_TYPES
        assert "none" in CTA_TYPES

    def test_frequency_labels_frozenset(self):
        from core.competitive_intelligence.schemas import FREQUENCY_LABELS
        assert isinstance(FREQUENCY_LABELS, frozenset)
        assert "daily" in FREQUENCY_LABELS

    def test_trend_rank_to_dict_matches_plan_format(self):
        from core.competitive_intelligence.schemas import TrendRank
        rank = TrendRank(
            account="@luxurybrand",
            style="premium tech",  # plan specifies human-readable
            engagement_rate=0.045,
            viral_score=0.82,
            patterns=("hook-first caption", "center product framing", "high contrast lighting"),
        )
        d = rank.to_dict()
        assert d["account"] == "@luxurybrand"
        assert d["style"] == "premium tech"
        assert isinstance(d["patterns"], list)
        assert len(d["patterns"]) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Competitor Registry
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompetitorRegistry:
    def setup_method(self):
        from core.competitive_intelligence import competitor_registry as cr
        # Start with empty registry for each test
        cr._save_registry([])

    def test_add_competitor(self):
        from core.competitive_intelligence.competitor_registry import add_competitor, get_active_competitors
        account = add_competitor(username="@testbrand", platform="instagram", niche="tech", tags=["ai", "gadgets"])
        assert account.username == "@testbrand"
        assert account.platform == "instagram"
        assert "ai" in account.tags

        active = get_active_competitors()
        assert len(active) == 1

    def test_add_duplicate_returns_existing(self):
        from core.competitive_intelligence.competitor_registry import add_competitor
        a1 = add_competitor("@dup", "instagram")
        a2 = add_competitor("@dup", "instagram")  # case-insensitive
        assert a1.account_id == a2.account_id

    def test_remove_competitor(self):
        from core.competitive_intelligence.competitor_registry import add_competitor, remove_competitor, get_active_competitors
        account = add_competitor("@toremove", "tiktok")
        assert remove_competitor(account.account_id) is True
        assert len(get_active_competitors()) == 0

    def test_remove_nonexistent(self):
        from core.competitive_intelligence.competitor_registry import remove_competitor
        assert remove_competitor("nonexistent_id") is False

    def test_get_by_platform(self):
        from core.competitive_intelligence.competitor_registry import add_competitor, get_by_platform
        add_competitor("@ig1", "instagram")
        add_competitor("@ig2", "instagram")
        add_competitor("@tk1", "tiktok")
        ig = get_by_platform("instagram")
        assert len(ig) == 2
        tk = get_by_platform("tiktok")
        assert len(tk) == 1

    def test_get_by_niche(self):
        from core.competitive_intelligence.competitor_registry import add_competitor, get_by_niche
        add_competitor("@a", "instagram", niche="fitness")
        add_competitor("@b", "tiktok", niche="fitness")
        add_competitor("@c", "instagram", niche="beauty")
        assert len(get_by_niche("fitness")) == 2

    def test_count(self):
        from core.competitive_intelligence.competitor_registry import add_competitor, count
        add_competitor("@a", "ig")
        add_competitor("@b", "ig")
        assert count() == 2

    def test_list_all_includes_inactive(self):
        from core.competitive_intelligence.competitor_registry import add_competitor, remove_competitor, list_all
        account = add_competitor("@inactive", "ig")
        remove_competitor(account.account_id)
        all_entries = list_all()
        assert len(all_entries) == 1
        assert all_entries[0]["active"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# Public Scraper
# ═══════════════════════════════════════════════════════════════════════════════

class TestPublicScraper:
    def test_fingerprint_raw_post_basic(self):
        from core.competitive_intelligence.public_scraper import fingerprint_raw_post
        from core.competitive_intelligence.schemas import CompetitorAccount, PublicPostFingerprint

        account = CompetitorAccount(account_id="acc1", username="@test", platform="instagram", niche="tech")
        fp = fingerprint_raw_post(
            account=account,
            caption="Este producto cambió mi vida! Link en bio 👆",
            visual_style="luxury_dark",
            likes=1000,
            comments=50,
            follower_count=10000,
        )
        assert isinstance(fp, PublicPostFingerprint)
        assert fp.account_id == "acc1"
        assert fp.hook_type != "unknown"
        assert fp.cta_type == "link_in_bio"  # "Link en bio" is explicitly link_in_bio
        assert fp.has_emoji is True
        assert fp.engagement_rate > 0

    def test_fingerprint_raw_post_no_followers(self):
        from core.competitive_intelligence.public_scraper import fingerprint_raw_post
        from core.competitive_intelligence.schemas import CompetitorAccount

        account = CompetitorAccount(account_id="acc1", username="@test", platform="ig", niche="x")
        fp = fingerprint_raw_post(account, caption="hola", follower_count=0)
        assert fp.engagement_rate == 0.0

    def test_hook_detection_question_led(self):
        from core.competitive_intelligence.public_scraper import fingerprint_raw_post
        from core.competitive_intelligence.schemas import CompetitorAccount
        account = CompetitorAccount(account_id="a", username="@q", platform="ig", niche="x")
        fp = fingerprint_raw_post(account, caption="¿Cansado de productos que no funcionan?")
        assert fp.hook_type in ("question_led",)

    def test_hook_detection_storytelling(self):
        from core.competitive_intelligence.public_scraper import fingerprint_raw_post
        from core.competitive_intelligence.schemas import CompetitorAccount
        account = CompetitorAccount(account_id="a", username="@s", platform="ig", niche="x")
        fp = fingerprint_raw_post(account, caption="Cuando empecé este proyecto, no tenía nada.")
        assert fp.hook_type in ("storytelling",)

    def test_cta_detection_link_in_bio(self):
        from core.competitive_intelligence.public_scraper import fingerprint_raw_post
        from core.competitive_intelligence.schemas import CompetitorAccount
        account = CompetitorAccount(account_id="a", username="@l", platform="ig", niche="x")
        fp = fingerprint_raw_post(account, caption="Link en la bio para más info!")
        assert fp.cta_type in ("link_in_bio", "soft_mention")

    def test_cta_detection_shop_now(self):
        from core.competitive_intelligence.public_scraper import fingerprint_raw_post
        from core.competitive_intelligence.schemas import CompetitorAccount
        account = CompetitorAccount(account_id="a", username="@s", platform="ig", niche="x")
        fp = fingerprint_raw_post(account, caption="Compra ya antes que se agote!")
        assert fp.cta_type == "shop_now"

    def test_structural_features_detected(self):
        from core.competitive_intelligence.public_scraper import fingerprint_raw_post
        from core.competitive_intelligence.schemas import CompetitorAccount
        account = CompetitorAccount(account_id="a", username="@f", platform="ig", niche="x")
        fp = fingerprint_raw_post(account, caption="Hola 🎉. Esto es increíble. #review #tech")
        assert fp.has_emoji is True
        assert fp.emoji_count > 0
        assert fp.has_hashtags is True
        assert fp.hashtag_count >= 2
        assert fp.sentence_count >= 2

    def test_fingerprint_account_generates_fingerprints(self):
        from core.competitive_intelligence.public_scraper import fingerprint_account
        from core.competitive_intelligence.schemas import CompetitorAccount
        account = CompetitorAccount(account_id="acc1", username="@test", platform="instagram", niche="tech")
        fps = fingerprint_account(account, max_posts=20)
        assert len(fps) == 20
        assert all(fp.account_id == "acc1" for fp in fps)

    def test_fingerprint_account_capped_at_50(self):
        from core.competitive_intelligence.public_scraper import fingerprint_account
        from core.competitive_intelligence.schemas import CompetitorAccount
        account = CompetitorAccount(account_id="acc1", username="@test", platform="instagram", niche="tech")
        fps = fingerprint_account(account, max_posts=200)
        assert len(fps) <= 50


# ═══════════════════════════════════════════════════════════════════════════════
# Visual Pattern Extractor
# ═══════════════════════════════════════════════════════════════════════════════

class TestVisualPatternExtractor:
    def test_classify_luxury_dark(self):
        from core.competitive_intelligence.visual_pattern_extractor import classify_visual_style
        style, conf, palette, comp = classify_visual_style(
            description="Dark background with gold accents, luxury product photography",
        )
        assert style == "luxury_dark"
        assert conf > 0

    def test_classify_minimal_clean(self):
        from core.competitive_intelligence.visual_pattern_extractor import classify_visual_style
        style, conf, palette, comp = classify_visual_style(
            description="Clean white background, minimal design, simple layout",
        )
        assert style == "minimal_clean"

    def test_classify_tech_premium(self):
        from core.competitive_intelligence.visual_pattern_extractor import classify_visual_style
        style, conf, palette, comp = classify_visual_style(
            description="Blue neon lighting, futuristic tech product, digital aesthetic",
        )
        assert style == "tech_premium"

    def test_classify_warm_lifestyle(self):
        from core.competitive_intelligence.visual_pattern_extractor import classify_visual_style
        style, conf, palette, comp = classify_visual_style(
            description="Warm natural sunlight, cozy home setting, lifestyle photography",
        )
        assert style == "warm_lifestyle"

    def test_classify_unknown_style(self):
        from core.competitive_intelligence.visual_pattern_extractor import classify_visual_style
        style, conf, palette, comp = classify_visual_style(description="xyz random text")
        assert style == "unknown"
        assert conf == 0.0

    def test_palette_inference(self):
        from core.competitive_intelligence.visual_pattern_extractor import classify_visual_style
        _, _, palette, _ = classify_visual_style(description="Dark background, black theme")
        assert palette == "dark_monochrome"

    def test_composition_inference(self):
        from core.competitive_intelligence.visual_pattern_extractor import classify_visual_style
        _, _, _, comp = classify_visual_style(description="Product centered in frame")
        assert comp == "center_product"

    def test_classify_batch(self):
        from core.competitive_intelligence.visual_pattern_extractor import classify_batch
        results = classify_batch([
            {"description": "Dark luxury gold accents"},
            {"description": "Clean white minimal"},
            {"description": "Warm home lifestyle"},
        ])
        assert len(results) == 3
        assert results[0][0] == "luxury_dark"
        assert results[1][0] == "minimal_clean"

    def test_never_raises(self):
        from core.competitive_intelligence.visual_pattern_extractor import classify_visual_style
        with patch("core.competitive_intelligence.visual_pattern_extractor._dispatch_classify", side_effect=RuntimeError("boom")):
            style, conf, palette, comp = classify_visual_style("anything")
            assert style in ("unknown", "luxury_dark", "minimal_clean", "warm_lifestyle", "cinematic_commercial", "tech_premium")


# ═══════════════════════════════════════════════════════════════════════════════
# Caption Analyzer
# ═══════════════════════════════════════════════════════════════════════════════

class TestCaptionAnalyzer:
    def test_analyze_question_led(self):
        from core.competitive_intelligence.caption_analyzer import analyze_caption
        result = analyze_caption("¿Cansado de cremas que no funcionan? Esta cambió mi piel en 7 días.")
        assert result["hook_type"] == "question_led"

    def test_analyze_storytelling(self):
        from core.competitive_intelligence.caption_analyzer import analyze_caption
        result = analyze_caption("Cuando empecé este negocio hace 3 años no tenía nada. Hoy facturo 6 cifras.")
        assert result["hook_type"] == "storytelling"

    def test_analyze_curiosity_gap(self):
        from core.competitive_intelligence.caption_analyzer import analyze_caption
        result = analyze_caption("Imagina un producto que se paga solo en 30 días...")
        assert result["hook_type"] == "curiosity_gap"

    def test_analyze_pain_point(self):
        from core.competitive_intelligence.caption_analyzer import analyze_caption
        result = analyze_caption("Cansado de gastar dinero en productos que no sirven.")
        assert result["hook_type"] in ("pain_point", "question_led")  # "cansado" is shared

    def test_cta_detection_link_in_bio(self):
        from core.competitive_intelligence.caption_analyzer import analyze_caption
        result = analyze_caption("Este producto es increíble. Link en la bio para más info 🔗")
        assert result["cta_type"] in ("link_in_bio", "soft_mention")

    def test_cta_comment_keyword(self):
        from core.competitive_intelligence.caption_analyzer import analyze_caption
        result = analyze_caption("Comenta 'INFO' y te mando el link directo al DM")
        assert result["cta_type"] == "comment_keyword"

    def test_language_detection_spanish(self):
        from core.competitive_intelligence.caption_analyzer import analyze_caption
        result = analyze_caption("Este producto es el mejor del mercado para el cuidado de la piel con ingredientes naturales y con resultados probados")
        assert result["language"] == "es"

    def test_language_detection_english(self):
        from core.competitive_intelligence.caption_analyzer import analyze_caption
        result = analyze_caption("This product is the best on the market for skincare with natural ingredients and proven results for your daily routine")
        assert result["language"] == "en"

    def test_structural_features(self):
        from core.competitive_intelligence.caption_analyzer import analyze_caption
        result = analyze_caption("Hola 🎉. Esto es genial. #review #tech ¿No crees?")
        assert result["features"]["has_emoji"] is True
        assert result["features"]["has_hashtags"] is True
        assert result["features"]["has_question"] is True

    def test_summarize_patterns(self):
        from core.competitive_intelligence.caption_analyzer import analyze_caption, summarize_patterns
        captions = [
            "¿Cansado de X? Link en bio.",
            "Cuando empecé... link en la descripción.",
            "Imagina que... link en bio.",
        ]
        analyses = [analyze_caption(c) for c in captions]
        summary = summarize_patterns(analyses)
        assert "dominant_hook" in summary
        assert "hook_distribution" in summary
        assert "top_patterns" in summary

    def test_analyze_batch(self):
        from core.competitive_intelligence.caption_analyzer import analyze_caption, analyze_batch
        results = analyze_batch(["hola link bio", "compra ya", "qué opinas?"])
        assert len(results) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Insight Engine
# ═══════════════════════════════════════════════════════════════════════════════

class TestInsightEngine:
    def test_build_insights_empty(self):
        from core.competitive_intelligence.insight_engine import build_insights
        from core.competitive_intelligence.schemas import CompetitorAccount
        account = CompetitorAccount(account_id="a", username="@x", platform="ig", niche="x")
        insight = build_insights(account, [])
        assert insight.account_id == "a"
        assert insight.dominant_style == "unknown"
        assert insight.avg_engagement_rate == 0.0

    def test_build_insights_with_data(self):
        from core.competitive_intelligence.insight_engine import build_insights
        from core.competitive_intelligence.schemas import CompetitorAccount, PublicPostFingerprint
        account = CompetitorAccount(account_id="a1", username="@b", platform="ig", niche="tech")
        fps = [
            PublicPostFingerprint(
                fingerprint_id=f"fp{i}", account_id="a1", platform="ig",
                collected_at="ts", hook_type="hook_first", cta_type="link_in_bio",
                sentence_count=3, avg_sentence_length=10.0, has_emoji=True,
                emoji_count=1, has_hashtags=False, hashtag_count=0, has_question=False,
                visual_style="luxury_dark", color_palette="dark", composition="center",
                text_overlay=False, engagement_rate=0.05,
            )
            for i in range(10)
        ]
        insight = build_insights(account, fps, posts_per_week_est=5.0)
        assert insight.dominant_style == "luxury_dark"
        assert insight.dominant_hook == "hook_first"
        assert insight.dominant_cta == "link_in_bio"
        assert insight.frequency_label == "weekly_few"

    def test_frequency_label_mapping(self):
        from core.competitive_intelligence.insight_engine import build_insights
        from core.competitive_intelligence.schemas import CompetitorAccount
        account = CompetitorAccount(account_id="a", username="@f", platform="ig", niche="x")
        tests = [
            (14.0, "multi_daily"),
            (7.0, "daily"),
            (3.0, "weekly_few"),
            (1.0, "weekly"),
            (0.5, "sparse"),
            (0.0, "irregular"),
        ]
        for freq, expected_label in tests:
            insight = build_insights(account, [], posts_per_week_est=freq)
            assert insight.frequency_label == expected_label, f"{freq} → {insight.frequency_label} (expected {expected_label})"

    def test_recommended_archetype_tags(self):
        from core.competitive_intelligence.insight_engine import build_insights
        from core.competitive_intelligence.schemas import CompetitorAccount, PublicPostFingerprint
        account = CompetitorAccount(account_id="a", username="@t", platform="ig", niche="x")
        fp = PublicPostFingerprint(
            fingerprint_id="fp", account_id="a", platform="ig",
            collected_at="ts", hook_type="question_led", cta_type="link_in_bio",
            sentence_count=2, avg_sentence_length=10.0, has_emoji=True,
            emoji_count=1, has_hashtags=False, hashtag_count=0, has_question=True,
            visual_style="tech_premium", color_palette="cool", composition="center",
            text_overlay=False, engagement_rate=0.03,
        )
        insight = build_insights(account, [fp])
        assert "tech_premium" in insight.recommended_archetype_tags
        assert "question_led" in insight.recommended_archetype_tags

    def test_build_all_insights(self):
        from core.competitive_intelligence.insight_engine import build_all_insights
        from core.competitive_intelligence.schemas import CompetitorAccount, PublicPostFingerprint
        a1 = CompetitorAccount(account_id="a1", username="@a", platform="ig", niche="x")
        a2 = CompetitorAccount(account_id="a2", username="@b", platform="ig", niche="x")
        fp = PublicPostFingerprint(
            fingerprint_id="fp", account_id="a1", platform="ig",
            collected_at="ts", hook_type="hook_first", cta_type="none",
            sentence_count=1, avg_sentence_length=5.0, has_emoji=False,
            emoji_count=0, has_hashtags=False, hashtag_count=0, has_question=False,
            visual_style="minimal_clean", color_palette="light", composition="flat",
            text_overlay=False, engagement_rate=0.02,
        )
        insights = build_all_insights([(a1, [fp], 3.0), (a2, [fp], 1.0)])
        assert len(insights) == 2
        assert insights[0].account_id == "a1"
        assert insights[1].account_id == "a2"


# ═══════════════════════════════════════════════════════════════════════════════
# Trend Ranker
# ═══════════════════════════════════════════════════════════════════════════════

class TestTrendRanker:
    def test_rank_trends_sorts_by_viral_score(self):
        from core.competitive_intelligence.trend_ranker import rank_trends
        from core.competitive_intelligence.schemas import CompetitorInsight

        i1 = CompetitorInsight(
            account_id="a1", username="low", platform="ig", analyzed_at="ts",
            avg_engagement_rate=0.01, estimated_posts_per_week=1.0,
            frequency_label="weekly", dominant_style="minimal_clean",
            style_distribution={"minimal_clean": 1.0}, dominant_hook="hook_first",
            hook_distribution={"hook_first": 1.0}, dominant_cta="none",
            cta_distribution={"none": 1.0}, viral_score=0.0,
            top_patterns=(), recommended_archetype_tags=(),
        )
        i2 = CompetitorInsight(
            account_id="a2", username="high", platform="ig", analyzed_at="ts",
            avg_engagement_rate=0.08, estimated_posts_per_week=14.0,
            frequency_label="multi_daily", dominant_style="tech_premium",
            style_distribution={"tech_premium": 1.0}, dominant_hook="question_led",
            hook_distribution={"question_led": 1.0}, dominant_cta="link_in_bio",
            cta_distribution={"link_in_bio": 1.0}, viral_score=0.0,
            top_patterns=(), recommended_archetype_tags=(),
        )

        trends = rank_trends([i1, i2])
        assert len(trends) == 2
        assert trends[0].account == "high"  # higher engagement → higher rank
        assert trends[1].account == "low"

    def test_rank_trends_empty(self):
        from core.competitive_intelligence.trend_ranker import rank_trends
        assert rank_trends([]) == []

    def test_rank_trends_single(self):
        from core.competitive_intelligence.trend_ranker import rank_trends
        from core.competitive_intelligence.schemas import CompetitorInsight
        i = CompetitorInsight(
            account_id="a1", username="solo", platform="ig", analyzed_at="ts",
            avg_engagement_rate=0.05, estimated_posts_per_week=7.0,
            frequency_label="daily", dominant_style="luxury_dark",
            style_distribution={"luxury_dark": 1.0}, dominant_hook="storytelling",
            hook_distribution={"storytelling": 1.0}, dominant_cta="soft_mention",
            cta_distribution={"soft_mention": 1.0}, viral_score=0.0,
            top_patterns=("luxury dark aesthetic",), recommended_archetype_tags=(),
        )
        trends = rank_trends([i])
        assert len(trends) == 1
        assert trends[0].viral_score > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Report Generator
# ═══════════════════════════════════════════════════════════════════════════════

class TestReportGenerator:
    def test_generate_report(self):
        from core.competitive_intelligence.report_generator import generate_report
        from core.competitive_intelligence.schemas import CompetitorInsight, TrendRank

        insight = CompetitorInsight(
            account_id="a1", username="@best", platform="ig", analyzed_at="ts",
            avg_engagement_rate=0.06, estimated_posts_per_week=10.0,
            frequency_label="daily", dominant_style="tech_premium",
            style_distribution={"tech_premium": 1.0}, dominant_hook="question_led",
            hook_distribution={"question_led": 1.0}, dominant_cta="link_in_bio",
            cta_distribution={"link_in_bio": 1.0}, viral_score=0.9,
            top_patterns=("tech premium aesthetic", "question-led opening"),
            recommended_archetype_tags=("tech_premium", "question_led"),
        )
        trend = TrendRank(
            account="@best", style="tech_premium",
            engagement_rate=0.06, viral_score=0.9,
            patterns=("tech premium aesthetic", "question-led opening"),
        )

        report = generate_report(trends=[trend], insights=[insight])
        assert report.accounts_analyzed == 1
        assert len(report.trends) == 1
        assert len(report.global_insights) > 0
        assert len(report.archetype_feeds) > 0

    def test_generate_report_empty(self):
        from core.competitive_intelligence.report_generator import generate_report
        report = generate_report(trends=[], insights=[])
        assert report.accounts_analyzed == 0
        assert len(report.trends) == 0

    def test_report_to_dict(self):
        from core.competitive_intelligence.report_generator import generate_report
        from core.competitive_intelligence.schemas import CompetitorInsight, TrendRank

        insight = CompetitorInsight(
            account_id="a1", username="@test", platform="ig", analyzed_at="ts",
            avg_engagement_rate=0.04, estimated_posts_per_week=3.0,
            frequency_label="weekly_few", dominant_style="minimal_clean",
            style_distribution={"minimal_clean": 1.0}, dominant_hook="hook_first",
            hook_distribution={"hook_first": 1.0}, dominant_cta="none",
            cta_distribution={"none": 1.0}, viral_score=0.5,
            top_patterns=(), recommended_archetype_tags=(),
        )
        trend = TrendRank(account="@test", style="minimal_clean", engagement_rate=0.04, viral_score=0.5, patterns=())
        report = generate_report(trends=[trend], insights=[insight])
        d = report.to_dict()
        assert isinstance(d, dict)
        assert d["accounts_analyzed"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: Full Pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    def test_end_to_end_workflow(self):
        """Complete pipeline: registry → fingerprint → insights → rank → report."""
        from core.competitive_intelligence.competitor_registry import add_competitor
        from core.competitive_intelligence.public_scraper import fingerprint_raw_post
        from core.competitive_intelligence.insight_engine import build_insights
        from core.competitive_intelligence.trend_ranker import rank_trends
        from core.competitive_intelligence.report_generator import generate_report

        # 1. Add competitors
        acc1 = add_competitor("@luxurybrand", "instagram", niche="luxury")
        acc2 = add_competitor("@techgadgets", "instagram", niche="tech")

        # 2. Fingerprint posts (using raw_post for real caption analysis)
        fps1 = [
            fingerprint_raw_post(acc1,
                caption="Imagina despertar con una piel perfecta. Este serum lo hace posible. Link en bio ✨",
                visual_style="luxury_dark", likes=5000, comments=200, follower_count=100000,
            ),
            fingerprint_raw_post(acc1,
                caption="¿Cansado de productos baratos que no funcionan? Nosotros solo usamos ingredientes premium.",
                visual_style="luxury_dark", likes=3000, comments=150, follower_count=100000,
            ),
        ]
        fps2 = [
            fingerprint_raw_post(acc2,
                caption="Este gadget cambió mi setup para siempre. Compra ya antes que se agote.",
                visual_style="tech_premium", likes=8000, comments=400, follower_count=200000,
            ),
            fingerprint_raw_post(acc2,
                caption="Cuando empecé en tech no tenía ni idea. Hoy te cuento mi TOP 5 gadgets 2026.",
                visual_style="tech_premium", likes=12000, comments=600, follower_count=200000,
            ),
        ]

        # 3. Build insights
        i1 = build_insights(acc1, fps1, posts_per_week_est=5.0)
        i2 = build_insights(acc2, fps2, posts_per_week_est=14.0)

        assert i1.dominant_style == "luxury_dark"
        assert i2.dominant_style == "tech_premium"

        # 4. Rank trends
        trends = rank_trends([i1, i2])
        assert len(trends) == 2

        # 5. Generate report
        report = generate_report(trends, [i1, i2])
        assert report.accounts_analyzed == 2
        assert len(report.global_insights) > 0

    def test_pipeline_output_matches_plan_format(self):
        """Verify the output format matches the plan's spec."""
        from core.competitive_intelligence.competitor_registry import add_competitor
        from core.competitive_intelligence.public_scraper import fingerprint_raw_post
        from core.competitive_intelligence.insight_engine import build_insights
        from core.competitive_intelligence.trend_ranker import rank_trends

        acc = add_competitor("@test", "instagram", niche="tech")
        fp = fingerprint_raw_post(acc,
            caption="Este producto es increíble. Link en bio.",
            visual_style="tech_premium", likes=100, comments=10, follower_count=1000,
        )
        insight = build_insights(acc, [fp])
        trends = rank_trends([insight])

        # Plan spec format:
        # [{"account": "...", "style": "...", "engagement_rate": 0.0, "viral_score": 0.0, "patterns": [...]}]
        output = [t.to_dict() for t in trends]
        assert isinstance(output, list)
        assert "account" in output[0]
        assert "style" in output[0]
        assert "engagement_rate" in output[0]
        assert "viral_score" in output[0]
        assert "patterns" in output[0]


# ═══════════════════════════════════════════════════════════════════════════════
# Isolation: No cross-layer contamination
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsolation:
    def test_ci_never_imports_flow_operator(self):
        import inspect
        from core.competitive_intelligence import report_generator as rg
        src = inspect.getsource(rg)
        assert "flow_operator" not in src.lower()
        assert "master_pipeline" not in src.lower()

    def test_ci_never_imports_revenue_layer(self):
        import inspect
        from core.competitive_intelligence import public_scraper as ps
        src = inspect.getsource(ps)
        assert "revenue_layer" not in src.lower()

    def test_ci_never_imports_dispatch_gate(self):
        import inspect
        from core.competitive_intelligence import trend_ranker as tr
        src = inspect.getsource(tr)
        assert "dispatch_gate" not in src

    def test_ci_never_calls_providers_directly(self):
        import inspect
        from core.competitive_intelligence import visual_pattern_extractor as vpe
        src = inspect.getsource(vpe)
        for banned in ["anthropic.", "gemini.", "groq.", "openai."]:
            assert banned not in src, f"Found direct provider call: {banned}"

    def test_ci_only_uses_dispatch_for_ai(self):
        """Visual pattern extractor uses dispatch, not direct calls."""
        import inspect
        from core.competitive_intelligence import visual_pattern_extractor as vpe
        src = inspect.getsource(vpe)
        assert "dispatch(" in src or "dispatch" not in src  # either uses dispatch or none at all

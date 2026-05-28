#!/usr/bin/env python3
"""
test_ci_to_vi_bridge.py — Tests for CI→VI bridge and scheduler.

Coverage:
- feed_insights_to_vi: empty, single, batch, errors, skipped
- feed_report_to_vi: wrapper delegation
- run_ci_pipeline: empty registry, with data, error paths
- Isolation: no flow_operator, revenue_layer, dispatch_gate imports
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_IMPERIO_ROOT = Path(__file__).parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))


# ═══════════════════════════════════════════════════════════════════════════════
# CI → VI Bridge
# ═══════════════════════════════════════════════════════════════════════════════

class TestCIToVIBridge:
    def test_feed_empty_insights(self):
        from core.competitive_intelligence.ci_to_vi_bridge import feed_insights_to_vi
        result = feed_insights_to_vi([])
        assert result["fed"] == 0
        assert result["skipped"] == 0
        assert result["errors"] == 0

    def test_feed_skips_unknown_style(self):
        from core.competitive_intelligence.ci_to_vi_bridge import feed_insights_to_vi
        from core.competitive_intelligence.schemas import CompetitorInsight
        insight = CompetitorInsight(
            account_id="a", username="@x", platform="ig", analyzed_at="ts",
            avg_engagement_rate=0.0, estimated_posts_per_week=0.0,
            frequency_label="irregular", dominant_style="unknown",
            style_distribution={}, dominant_hook="unknown",
            hook_distribution={}, dominant_cta="none",
            cta_distribution={}, viral_score=0.0,
            top_patterns=(), recommended_archetype_tags=(),
        )
        result = feed_insights_to_vi([insight])
        assert result["fed"] == 0
        assert result["skipped"] == 1

    def test_feed_single_insight(self):
        from core.competitive_intelligence.ci_to_vi_bridge import feed_insights_to_vi
        from core.competitive_intelligence.schemas import CompetitorInsight

        insight = CompetitorInsight(
            account_id="a1", username="@lux", platform="instagram", analyzed_at="ts",
            avg_engagement_rate=0.06, estimated_posts_per_week=5.0,
            frequency_label="weekly_few", dominant_style="luxury_dark",
            style_distribution={"luxury_dark": 1.0}, dominant_hook="question_led",
            hook_distribution={"question_led": 1.0}, dominant_cta="link_in_bio",
            cta_distribution={"link_in_bio": 1.0}, viral_score=0.0,
            top_patterns=(), recommended_archetype_tags=("luxury_dark", "question_led"),
        )

        # Mock upsert_archetype to avoid numpy centroid issues + file I/O
        import core.visual_intelligence.archetype_memory as am
        original_upsert = am.upsert_archetype
        calls = []

        def mock_upsert(category, name, style_labels, centroid, revenue, similarity):
            calls.append({
                "category": category, "name": name,
                "style_labels": style_labels, "revenue": revenue, "similarity": similarity,
            })

        am.upsert_archetype = mock_upsert
        try:
            result = feed_insights_to_vi([insight])
            assert result["fed"] == 1
            assert result["skipped"] == 0
            assert result["errors"] == 0
            assert result["category"] == "competitive_intelligence"
            assert len(calls) == 1
            assert "DARK_LUXURY_CINEMATIC" in calls[0]["style_labels"]
        finally:
            am.upsert_archetype = original_upsert

    def test_feed_custom_category(self):
        from core.competitive_intelligence.ci_to_vi_bridge import feed_insights_to_vi
        from core.competitive_intelligence.schemas import CompetitorInsight
        import core.visual_intelligence.archetype_memory as am
        original_upsert = am.upsert_archetype
        calls = []

        def mock_upsert(category, name, style_labels, centroid, revenue, similarity):
            calls.append({"category": category})

        am.upsert_archetype = mock_upsert
        try:
            insight = CompetitorInsight(
                account_id="a", username="@t", platform="ig", analyzed_at="ts",
                avg_engagement_rate=0.05, estimated_posts_per_week=3.0,
                frequency_label="weekly_few", dominant_style="tech_premium",
                style_distribution={"tech_premium": 1.0}, dominant_hook="hook_first",
                hook_distribution={"hook_first": 1.0}, dominant_cta="none",
                cta_distribution={}, viral_score=0.0,
                top_patterns=(), recommended_archetype_tags=("tech_premium",),
            )
            result = feed_insights_to_vi([insight], category="custom_cat")
            assert result["fed"] == 1
            assert calls[0]["category"] == "custom_cat"
        finally:
            am.upsert_archetype = original_upsert

    def test_feed_handles_upsert_errors_gracefully(self):
        from core.competitive_intelligence.ci_to_vi_bridge import feed_insights_to_vi
        from core.competitive_intelligence.schemas import CompetitorInsight
        import core.visual_intelligence.archetype_memory as am
        original_upsert = am.upsert_archetype

        def mock_upsert_broken(*args, **kwargs):
            raise RuntimeError("disk full")

        am.upsert_archetype = mock_upsert_broken
        try:
            insight = CompetitorInsight(
                account_id="a", username="@e", platform="ig", analyzed_at="ts",
                avg_engagement_rate=0.05, estimated_posts_per_week=3.0,
                frequency_label="weekly_few", dominant_style="warm_lifestyle",
                style_distribution={"warm_lifestyle": 1.0}, dominant_hook="storytelling",
                hook_distribution={"storytelling": 1.0}, dominant_cta="soft_mention",
                cta_distribution={"soft_mention": 1.0}, viral_score=0.0,
                top_patterns=(), recommended_archetype_tags=("warm_lifestyle",),
            )
            result = feed_insights_to_vi([insight])
            assert result["fed"] == 0
            assert result["errors"] == 1
        finally:
            am.upsert_archetype = original_upsert

    def test_feed_report_to_vi_delegates(self):
        from core.competitive_intelligence.ci_to_vi_bridge import feed_report_to_vi
        from core.competitive_intelligence.schemas import CompetitorInsight
        # Empty insights → zero fed
        result = feed_report_to_vi(trends=[], insights=[], category="test")
        assert result["fed"] == 0
        assert result["category"] == "test"

    def test_ci_style_mapping_coverage(self):
        """Verify CI styles have VI mappings."""
        from core.competitive_intelligence.ci_to_vi_bridge import _CI_STYLE_TO_VI_LABEL
        from core.competitive_intelligence.schemas import VISUAL_STYLES
        # All CI visual styles should have a mapping (even if empty string)
        for style in VISUAL_STYLES:
            assert style in _CI_STYLE_TO_VI_LABEL, f"Missing VI mapping for CI style: {style}"


# ═══════════════════════════════════════════════════════════════════════════════
# CI Scheduler
# ═══════════════════════════════════════════════════════════════════════════════

class TestCIScheduler:
    def test_run_pipeline_empty_registry(self):
        """Pipeline with no competitors should return clean summary."""
        from core.competitive_intelligence import competitor_registry as cr
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline

        # Save current registry, then clear
        original_registry = cr._load_registry()
        cr._save_registry([])
        try:
            summary = run_ci_pipeline()
            assert summary["status"] == "ok"
            assert summary["competitors"] == 0
            assert summary["insights"] == 0
        finally:
            cr._save_registry(original_registry)

    def test_run_pipeline_with_data(self):
        """Pipeline with one competitor should produce insights and feed VI."""
        from core.competitive_intelligence import competitor_registry as cr
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline
        import core.visual_intelligence.archetype_memory as am
        original_upsert = am.upsert_archetype

        upsert_calls = []
        def mock_upsert(category, name, style_labels, centroid, revenue, similarity):
            upsert_calls.append({"category": category, "name": name})

        am.upsert_archetype = mock_upsert

        # Save current registry, add one competitor
        original_registry = cr._load_registry()
        cr._save_registry([])
        try:
            from core.competitive_intelligence.competitor_registry import add_competitor
            add_competitor("@testcompetitor", "instagram", niche="tech")

            summary = run_ci_pipeline(max_posts=5)
            assert summary["status"] == "ok"
            assert summary["competitors"] == 1
            assert summary["fingerprints"] == 5
            assert summary["insights"] == 1
            assert summary["trends"] == 1
            assert summary["vi_fed"] == 1
        finally:
            cr._save_registry(original_registry)
            am.upsert_archetype = original_upsert

    def test_run_pipeline_persists_report(self):
        """Pipeline should create report and summary files."""
        from core.competitive_intelligence import competitor_registry as cr
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline, _REPORT_DIR, _today_str
        import core.visual_intelligence.archetype_memory as am
        original_upsert = am.upsert_archetype
        am.upsert_archetype = lambda *a, **kw: None

        original_registry = cr._load_registry()
        cr._save_registry([])
        try:
            from core.competitive_intelligence.competitor_registry import add_competitor
            add_competitor("@persisttest", "instagram", niche="beauty")

            summary = run_ci_pipeline(max_posts=2)

            report_path = _REPORT_DIR / f"ci_report_{_today_str()}.json"
            summary_path = _REPORT_DIR / f"ci_summary_{_today_str()}.json"

            assert report_path.exists(), f"Report not created at {report_path}"
            assert summary_path.exists(), f"Summary not created at {summary_path}"

            # Verify report has expected structure
            import json
            report_data = json.loads(report_path.read_text())
            assert "accounts_analyzed" in report_data
            assert report_data["accounts_analyzed"] >= 1
        finally:
            cr._save_registry(original_registry)
            am.upsert_archetype = original_upsert

    def test_run_pipeline_handles_fingerprint_errors(self):
        """Pipeline should continue even if one account fails."""
        from core.competitive_intelligence import competitor_registry as cr
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline
        import core.visual_intelligence.archetype_memory as am
        original_upsert = am.upsert_archetype
        am.upsert_archetype = lambda *a, **kw: None

        original_registry = cr._load_registry()
        cr._save_registry([])
        try:
            from core.competitive_intelligence.competitor_registry import add_competitor
            add_competitor("@good", "instagram", niche="tech")

            # Force an error by patching fingerprint_account to fail
            import core.competitive_intelligence.public_scraper as ps
            original_fingerprint = ps.fingerprint_account

            def broken_fingerprint(account, max_posts=50):
                if account.username == "@good":
                    raise RuntimeError("API rate limited")
                return original_fingerprint(account, max_posts)

            ps.fingerprint_account = broken_fingerprint
            try:
                summary = run_ci_pipeline(max_posts=2)
                assert summary["status"] == "ok"
                assert summary["errors"] >= 1
            finally:
                ps.fingerprint_account = original_fingerprint
        finally:
            cr._save_registry(original_registry)
            am.upsert_archetype = original_upsert

    def test_run_background_loop_test_mode(self):
        """In CI_TEST_MODE, background loop runs once and exits."""
        import os
        os.environ["CI_TEST_MODE"] = "1"

        from core.competitive_intelligence.ci_scheduler import run_background_loop
        from core.competitive_intelligence import competitor_registry as cr

        original_registry = cr._load_registry()
        cr._save_registry([])

        import core.visual_intelligence.archetype_memory as am
        original_upsert = am.upsert_archetype
        am.upsert_archetype = lambda *a, **kw: None

        try:
            from core.competitive_intelligence.competitor_registry import add_competitor
            add_competitor("@looptest", "instagram", niche="tech")

            # Should run once and return (test mode)
            run_background_loop(interval_seconds=0.1, max_posts=2)
            # If we get here, it didn't loop forever — success
        finally:
            cr._save_registry(original_registry)
            am.upsert_archetype = original_upsert
            os.environ.pop("CI_TEST_MODE", None)


# ═══════════════════════════════════════════════════════════════════════════════
# Isolation: Bridge and Scheduler never import prohibited layers
# ═══════════════════════════════════════════════════════════════════════════════

class TestBridgeIsolation:
    def test_bridge_never_imports_flow_operator(self):
        import inspect
        import core.competitive_intelligence.ci_to_vi_bridge as b
        src = inspect.getsource(b)
        assert "flow_operator" not in src.lower()
        assert "master_pipeline" not in src.lower()

    def test_bridge_never_imports_revenue_layer(self):
        import inspect
        import core.competitive_intelligence.ci_to_vi_bridge as b
        src = inspect.getsource(b)
        assert "revenue_layer" not in src.lower()

    def test_bridge_never_imports_dispatch_gate(self):
        import inspect
        import core.competitive_intelligence.ci_to_vi_bridge as b
        src = inspect.getsource(b)
        assert "dispatch_gate" not in src

    def test_scheduler_never_imports_flow_operator(self):
        import inspect
        import core.competitive_intelligence.ci_scheduler as s
        src = inspect.getsource(s)
        assert "flow_operator" not in src.lower()
        assert "master_pipeline" not in src.lower()

    def test_scheduler_never_imports_revenue_layer(self):
        import inspect
        import core.competitive_intelligence.ci_scheduler as s
        src = inspect.getsource(s)
        assert "revenue_layer" not in src.lower()

    def test_scheduler_never_imports_dispatch_gate(self):
        import inspect
        import core.competitive_intelligence.ci_scheduler as s
        src = inspect.getsource(s)
        assert "dispatch_gate" not in src

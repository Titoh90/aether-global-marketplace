#!/usr/bin/env python3
"""
test_ci_scheduler.py — Tests for CI scheduler (pipeline runner + background loop).

Coverage:
- run_ci_pipeline: empty registry, with data, error resilience, VI feed
- run_background_loop: test mode behavior, error survival
- Integration: full scheduler pipeline end-to-end
- CLI: --run, --dry-run, --loop, --help
- Isolation: no cross-layer contamination
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

_IMPERIO_ROOT = Path(__file__).parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))


# ── Helper: monkey-patch archetype_memory.upsert_archetype ────────────────────

def _patch_upsert():
    """Replace upsert_archetype with a recording mock. Returns (mock, original)."""
    import core.visual_intelligence.archetype_memory as am
    original = am.upsert_archetype
    calls = []

    def mock_upsert(category, name, style_labels, centroid, revenue, similarity):
        calls.append({
            "category": category, "name": name,
            "style_labels": style_labels, "revenue": revenue, "similarity": similarity,
        })

    am.upsert_archetype = mock_upsert
    return calls, original


def _restore_upsert(original):
    import core.visual_intelligence.archetype_memory as am
    am.upsert_archetype = original


def _mock_upsert_noop():
    """Replace upsert_archetype with a no-op. Returns original."""
    import core.visual_intelligence.archetype_memory as am
    original = am.upsert_archetype
    am.upsert_archetype = lambda *a, **kw: None
    return original


# ── Helper: save/restore competitor registry ──────────────────────────────────

def _clear_registry():
    from core.competitive_intelligence import competitor_registry as cr
    original = cr._load_registry()
    cr._save_registry([])
    return original


def _restore_registry(original):
    from core.competitive_intelligence import competitor_registry as cr
    cr._save_registry(original)


# ═══════════════════════════════════════════════════════════════════════════════
# CI Scheduler — Pipeline Runner
# ═══════════════════════════════════════════════════════════════════════════════

class TestCISchedulerPipeline:
    def setup_method(self):
        os.environ["CI_TEST_MODE"] = "1"
        self._orig_registry = _clear_registry()

    def teardown_method(self):
        os.environ.pop("CI_TEST_MODE", None)
        _restore_registry(self._orig_registry)

    def test_run_pipeline_no_competitors(self):
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline
        orig_upsert = _mock_upsert_noop()
        try:
            result = run_ci_pipeline(max_posts=5)
            assert result["status"] == "ok"
            assert result["competitors"] == 0
            assert result["insights"] == 0
        finally:
            _restore_upsert(orig_upsert)

    def test_run_pipeline_with_competitors(self):
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline
        from core.competitive_intelligence.competitor_registry import add_competitor

        calls, orig_upsert = _patch_upsert()
        try:
            add_competitor("@testbrand", "instagram", niche="tech", tags=["ai"])
            result = run_ci_pipeline(max_posts=5)
            assert result["status"] == "ok"
            assert result["competitors"] == 1
            assert result["fingerprints"] == 5
            assert result["insights"] == 1
            assert result["trends"] == 1
            assert result["vi_fed"] == 1
        finally:
            _restore_upsert(orig_upsert)

    def test_run_pipeline_multiple_competitors(self):
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline
        from core.competitive_intelligence.competitor_registry import add_competitor

        orig_upsert = _mock_upsert_noop()
        try:
            add_competitor("@brand1", "instagram", niche="luxury")
            add_competitor("@brand2", "tiktok", niche="tech")
            add_competitor("@brand3", "instagram", niche="fitness")
            result = run_ci_pipeline(max_posts=3)
            assert result["competitors"] == 3
            assert result["insights"] == 3
            assert result["trends"] == 3
        finally:
            _restore_upsert(orig_upsert)

    def test_run_pipeline_vi_feed_called(self):
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline
        from core.competitive_intelligence.competitor_registry import add_competitor

        calls, orig_upsert = _patch_upsert()
        try:
            add_competitor("@vi_feed_test", "instagram", niche="tech")
            result = run_ci_pipeline(max_posts=3)
            assert len(calls) >= 1
            assert result["vi_fed"] == 1
        finally:
            _restore_upsert(orig_upsert)

    def test_run_pipeline_vi_feed_survives_error(self):
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline
        from core.competitive_intelligence.competitor_registry import add_competitor

        orig_upsert = _mock_upsert_noop()
        try:
            add_competitor("@resilient", "instagram", niche="tech")

            # Force an error in the bridge import
            import core.competitive_intelligence.ci_to_vi_bridge as br
            original_feed = br.feed_insights_to_vi

            def broken_feed(*args, **kwargs):
                raise RuntimeError("VI unavailable")

            br.feed_insights_to_vi = broken_feed
            try:
                result = run_ci_pipeline(max_posts=3)
                assert result["status"] == "ok"
                assert result["errors"] >= 1
            finally:
                br.feed_insights_to_vi = original_feed
        finally:
            _restore_upsert(orig_upsert)

    def test_run_pipeline_survives_fingerprint_failure(self):
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline
        from core.competitive_intelligence.competitor_registry import add_competitor

        orig_upsert = _mock_upsert_noop()
        try:
            add_competitor("@bad_account", "instagram", niche="x")

            import core.competitive_intelligence.public_scraper as ps
            original_fp = ps.fingerprint_account

            def broken_fp(account, max_posts=50):
                raise RuntimeError("API down")

            ps.fingerprint_account = broken_fp
            try:
                result = run_ci_pipeline(max_posts=3)
                assert result["status"] == "ok"
                assert result["errors"] >= 1
            finally:
                ps.fingerprint_account = original_fp
        finally:
            _restore_upsert(orig_upsert)

    def test_run_pipeline_survives_registry_failure(self):
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline

        orig_upsert = _mock_upsert_noop()
        try:
            import core.competitive_intelligence.competitor_registry as cr
            original_get = cr.get_active_competitors

            def broken_get():
                raise RuntimeError("Registry corrupted")

            cr.get_active_competitors = broken_get
            try:
                result = run_ci_pipeline(max_posts=3)
                assert result["status"] == "error"
                assert result["errors"] >= 1
            finally:
                cr.get_active_competitors = original_get
        finally:
            _restore_upsert(orig_upsert)

    def test_run_pipeline_summary_shape(self):
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline
        from core.competitive_intelligence.competitor_registry import add_competitor

        orig_upsert = _mock_upsert_noop()
        try:
            add_competitor("@shape_test", "instagram", niche="tech")
            result = run_ci_pipeline(max_posts=3)
            assert "run_at" in result
            assert "status" in result
            assert "competitors" in result
            assert "fingerprints" in result
            assert "insights" in result
            assert "trends" in result
            assert "vi_fed" in result
            assert "errors" in result
            assert "error_details" in result
        finally:
            _restore_upsert(orig_upsert)

    def test_run_pipeline_report_persisted(self):
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline
        from core.competitive_intelligence.competitor_registry import add_competitor

        orig_upsert = _mock_upsert_noop()
        try:
            add_competitor("@report_test", "instagram", niche="tech")

            # Patch report/log dirs to temp
            with tempfile.TemporaryDirectory() as tmpdir:
                import core.competitive_intelligence.ci_scheduler as cs
                orig_report = cs._REPORT_DIR
                orig_log = cs._LOG_DIR
                orig_report_created = cs._report_dir_created
                orig_log_created = cs._log_dir_created
                cs._REPORT_DIR = Path(tmpdir) / "reports"
                cs._LOG_DIR = Path(tmpdir) / "logs"
                cs._report_dir_created = False
                cs._log_dir_created = False
                try:
                    result = run_ci_pipeline(max_posts=3)
                    report_dir = Path(tmpdir) / "reports"
                    assert report_dir.exists()
                    report_files = list(report_dir.glob("ci_report_*.json"))
                    assert len(report_files) >= 1
                    report_data = json.loads(report_files[0].read_text())
                    assert "generated_at" in report_data
                    assert "accounts_analyzed" in report_data
                finally:
                    cs._REPORT_DIR = orig_report
                    cs._LOG_DIR = orig_log
                    cs._report_dir_created = orig_report_created
                    cs._log_dir_created = orig_log_created
        finally:
            _restore_upsert(orig_upsert)

    def test_run_pipeline_never_raises(self):
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline
        from core.competitive_intelligence.competitor_registry import add_competitor

        orig_upsert = _mock_upsert_noop()
        try:
            add_competitor("@never_fail", "instagram", niche="tech")

            import core.competitive_intelligence.public_scraper as ps
            original_fp = ps.fingerprint_account

            def broken_fp(account, max_posts=50):
                raise RuntimeError("fail")

            ps.fingerprint_account = broken_fp
            try:
                result = run_ci_pipeline(max_posts=3)
                assert result is not None
                assert result["insights"] == 0
            finally:
                ps.fingerprint_account = original_fp
        finally:
            _restore_upsert(orig_upsert)


# ═══════════════════════════════════════════════════════════════════════════════
# CI Scheduler — Background Loop
# ═══════════════════════════════════════════════════════════════════════════════

class TestCIBackgroundLoop:
    def setup_method(self):
        os.environ["CI_TEST_MODE"] = "1"
        self._orig_registry = _clear_registry()

    def teardown_method(self):
        os.environ.pop("CI_TEST_MODE", None)
        _restore_registry(self._orig_registry)

    def test_background_loop_runs_once_in_test_mode(self):
        from core.competitive_intelligence.ci_scheduler import run_background_loop
        from core.competitive_intelligence.competitor_registry import add_competitor

        orig_upsert = _mock_upsert_noop()
        try:
            add_competitor("@loop_test", "instagram", niche="tech")

            import core.competitive_intelligence.ci_scheduler as cs
            original_run = cs.run_ci_pipeline
            calls = []

            def track_run(*args, **kwargs):
                calls.append(1)
                return {"status": "ok", "competitors": 1, "fingerprints": 0,
                        "insights": 0, "trends": 0, "vi_fed": 0, "errors": 0, "error_details": []}

            cs.run_ci_pipeline = track_run
            try:
                run_background_loop(vi_category="test", max_posts=3)
                # In test mode, should call pipeline exactly once and return
                assert len(calls) == 1
            finally:
                cs.run_ci_pipeline = original_run
        finally:
            _restore_upsert(orig_upsert)

    def test_background_loop_survives_pipeline_error(self):
        from core.competitive_intelligence.ci_scheduler import run_background_loop

        orig_upsert = _mock_upsert_noop()
        try:
            import core.competitive_intelligence.ci_scheduler as cs
            original_run = cs.run_ci_pipeline

            def broken_run(*args, **kwargs):
                raise RuntimeError("boom")

            cs.run_ci_pipeline = broken_run
            try:
                # In test mode, should not propagate the error
                run_background_loop(max_posts=3)
            finally:
                cs.run_ci_pipeline = original_run
        finally:
            _restore_upsert(orig_upsert)

    def test_background_loop_with_interval(self):
        """Background loop accepts custom interval."""
        from core.competitive_intelligence.ci_scheduler import run_background_loop

        orig_upsert = _mock_upsert_noop()
        try:
            import core.competitive_intelligence.ci_scheduler as cs
            original_run = cs.run_ci_pipeline
            calls = []

            def track_run(*args, **kwargs):
                calls.append(1)
                return {"status": "ok", "competitors": 0, "fingerprints": 0,
                        "insights": 0, "trends": 0, "vi_fed": 0, "errors": 0, "error_details": []}

            cs.run_ci_pipeline = track_run
            try:
                run_background_loop(interval_seconds=3600, max_posts=5)
                assert len(calls) == 1
            finally:
                cs.run_ci_pipeline = original_run
        finally:
            _restore_upsert(orig_upsert)


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: Full scheduler pipeline end-to-end
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchedulerIntegration:
    def setup_method(self):
        os.environ["CI_TEST_MODE"] = "1"
        self._orig_registry = _clear_registry()

    def teardown_method(self):
        os.environ.pop("CI_TEST_MODE", None)
        _restore_registry(self._orig_registry)

    def test_full_scheduler_to_bridge_flow(self):
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline
        from core.competitive_intelligence.competitor_registry import add_competitor

        calls, orig_upsert = _patch_upsert()
        try:
            add_competitor("@endtoend", "instagram", niche="luxury")
            result = run_ci_pipeline(max_posts=5)

            assert result["status"] == "ok"
            assert result["competitors"] == 1
            assert result["insights"] == 1
            assert result["trends"] == 1
            assert result["vi_fed"] == 1

            # Verify upsert was actually called with correct args
            assert len(calls) >= 1
            call_kwargs = calls[0]
            assert call_kwargs["category"] == "competitive_intelligence"
            assert call_kwargs["name"].startswith("CI_")
            assert len(call_kwargs["style_labels"]) >= 1
        finally:
            _restore_upsert(orig_upsert)

    def test_scheduler_with_varying_post_counts(self):
        from core.competitive_intelligence.ci_scheduler import run_ci_pipeline
        from core.competitive_intelligence.competitor_registry import add_competitor

        orig_upsert = _mock_upsert_noop()
        try:
            add_competitor("@brand_a", "instagram", niche="tech")
            add_competitor("@brand_b", "tiktok", niche="luxury")
            result = run_ci_pipeline(max_posts=10)
            assert result["fingerprints"] == 20  # 10 per account × 2 accounts
        finally:
            _restore_upsert(orig_upsert)


# ═══════════════════════════════════════════════════════════════════════════════
# Isolation: No cross-layer contamination
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsolation:
    def test_scheduler_never_imports_flow_operator(self):
        import inspect
        import core.competitive_intelligence.ci_scheduler as cs
        src = inspect.getsource(cs)
        assert "flow_operator" not in src.lower()
        assert "master_pipeline" not in src.lower()

    def test_scheduler_never_imports_revenue_layer(self):
        import inspect
        import core.competitive_intelligence.ci_scheduler as cs
        src = inspect.getsource(cs)
        assert "revenue_layer" not in src.lower()

    def test_scheduler_never_imports_dispatch_gate_as_import(self):
        import inspect
        import re
        import core.competitive_intelligence.ci_scheduler as cs
        src = inspect.getsource(cs)
        # Check actual imports, not comments/docstrings
        import_lines = [l for l in src.split("\n") if l.strip().startswith(("import ", "from "))]
        for line in import_lines:
            assert "dispatch_gate" not in line, f"Found dispatch_gate import: {line.strip()}"

    def test_scheduler_never_imports_truth_layer(self):
        import inspect
        import core.competitive_intelligence.ci_scheduler as cs
        src = inspect.getsource(cs)
        assert "visual_truth" not in src.lower()

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

    def test_bridge_never_imports_dispatch_gate_as_import(self):
        import inspect
        import re
        import core.competitive_intelligence.ci_to_vi_bridge as b
        src = inspect.getsource(b)
        import_lines = [l for l in src.split("\n") if l.strip().startswith(("import ", "from "))]
        for line in import_lines:
            assert "dispatch_gate" not in line, f"Found dispatch_gate import: {line.strip()}"


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

class TestCLI:
    def test_cli_run_flag(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.competitive_intelligence.ci_scheduler", "--run"],
            capture_output=True, text=True, timeout=30,
            cwd=str(_IMPERIO_ROOT),
            env={**os.environ, "CI_TEST_MODE": "1"},
        )
        assert result.returncode == 0
        output = result.stdout.strip()
        assert output, "CLI --run produced no output"
        # Output should be valid JSON
        summary = json.loads(output)
        assert "status" in summary

    def test_cli_dry_run(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.competitive_intelligence.ci_scheduler", "--dry-run"],
            capture_output=True, text=True, timeout=30,
            cwd=str(_IMPERIO_ROOT),
            env={**os.environ, "CI_TEST_MODE": "1"},
        )
        assert result.returncode == 0
        output = result.stdout.strip()
        assert output, "CLI --dry-run produced no output"
        summary = json.loads(output)
        assert "status" in summary

    def test_cli_loop_test_mode(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.competitive_intelligence.ci_scheduler", "--loop"],
            capture_output=True, text=True, timeout=30,
            cwd=str(_IMPERIO_ROOT),
            env={**os.environ, "CI_TEST_MODE": "1"},
        )
        assert result.returncode == 0

    def test_cli_help(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.competitive_intelligence.ci_scheduler", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(_IMPERIO_ROOT),
        )
        assert result.returncode == 0
        stdout_lower = result.stdout.lower()
        assert "usage" in stdout_lower or "ci scheduler" in stdout_lower

    def test_cli_bridge_help(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.competitive_intelligence.ci_to_vi_bridge", "--help"],
            capture_output=True, text=True, timeout=10,
            cwd=str(_IMPERIO_ROOT),
        )
        assert result.returncode == 0
        stdout_lower = result.stdout.lower()
        assert "usage" in stdout_lower or "feed" in stdout_lower

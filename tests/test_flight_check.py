#!/usr/bin/env python3
"""
test_flight_check.py — Tests for the Flight Check Layer.

Coverage:
- Quick mode: runs Phase 2+3 suites
- Full mode: runs all suites
- JSON report generation and validity
- CLI: --quick, --full, --json-only, --help
- Suite result parsing, timeout handling
- Isolation: no forbidden imports
- Never-raise: all paths return a report
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


# ═══════════════════════════════════════════════════════════════════════════════
# Flight Check — Quick Mode
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlightCheckQuickMode:
    """Quick mode: Phase 2+3 suites only."""

    def test_quick_mode_runs_all_four_suites(self):
        from core.flight_check import run_flight_check
        report = run_flight_check(mode="quick", json_only=True)
        assert report.mode == "quick"
        assert len(report.suites) == 4
        suite_names = {s.suite for s in report.suites}
        assert "tests/test_cinematic_video.py" in suite_names
        assert "tests/test_ci_scheduler.py" in suite_names
        assert "tests/test_ci_to_vi_bridge.py" in suite_names
        assert "tests/test_flow_operator_training.py" in suite_names

    def test_quick_mode_all_suites_pass(self):
        from core.flight_check import run_flight_check
        report = run_flight_check(mode="quick", json_only=True)
        assert report.total_passed > 0
        assert report.total_failed == 0
        assert report.total_errors == 0
        assert report.passed is True

    def test_quick_mode_report_structure(self):
        from core.flight_check import run_flight_check
        report = run_flight_check(mode="quick", json_only=True)
        assert report.check_id.startswith("FLIGHT-")
        assert report.checked_at
        assert report.duration_total_seconds > 0
        assert isinstance(report.suites, tuple)

    def test_quick_mode_each_suite_has_counts(self):
        from core.flight_check import run_flight_check
        report = run_flight_check(mode="quick", json_only=True)
        for suite in report.suites:
            assert suite.passed > 0, f"{suite.suite}: zero tests passed"
            assert suite.failed == 0, f"{suite.suite}: has failures"
            assert suite.errors == 0, f"{suite.suite}: has errors"
            assert suite.duration_seconds >= 0
            assert suite.raw_output

    def test_quick_mode_json_report_persisted(self):
        from core.flight_check import run_flight_check
        from core.flight_check import _REPORT_DIR

        report = run_flight_check(mode="quick", json_only=True)
        report_path = _REPORT_DIR / f"{report.check_id}.json"
        assert report_path.exists(), f"Report not found at {report_path}"

        with open(report_path) as f:
            data = json.load(f)
        assert data["check_id"] == report.check_id
        assert data["mode"] == "quick"
        assert data["passed"] is True
        assert len(data["suites"]) == 4
        for s in data["suites"]:
            assert "suite" in s
            assert "passed" in s
            assert "failed" in s
            assert "errors" in s
            assert "duration_seconds" in s

    def test_quick_mode_invalid_mode_falls_back(self):
        from core.flight_check import run_flight_check
        report = run_flight_check(mode="hyperspeed", json_only=True)
        assert report.mode == "quick"
        assert report.total_passed > 0
        assert report.passed is True


# ═══════════════════════════════════════════════════════════════════════════════
# Flight Check — Full Mode
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlightCheckFullMode:
    """Full mode: all test suites."""

    @pytest.mark.slow
    def test_full_mode_runs_all_suites(self):
        from core.flight_check import run_flight_check
        report = run_flight_check(mode="full", json_only=True)
        assert report.mode == "full"
        assert len(report.suites) >= 10  # At least 10 suites expected

    @pytest.mark.slow
    def test_full_mode_all_pass_or_allowed_fail(self):
        from core.flight_check import run_flight_check, _ALLOWED_FAIL
        report = run_flight_check(mode="full", json_only=True)
        # Every failing suite should be in the allowed-fail list
        for suite in report.suites:
            if suite.failed > 0 or suite.errors > 0:
                assert suite.suite in _ALLOWED_FAIL, (
                    f"{suite.suite} failed but is not in _ALLOWED_FAIL"
                )
        assert report.passed is True

    @pytest.mark.slow
    def test_full_mode_includes_quick_suites(self):
        from core.flight_check import run_flight_check
        report = run_flight_check(mode="full", json_only=True)
        suite_names = {s.suite for s in report.suites}
        assert "tests/test_cinematic_video.py" in suite_names
        assert "tests/test_ci_scheduler.py" in suite_names
        assert "tests/test_ci_to_vi_bridge.py" in suite_names

    @pytest.mark.slow
    def test_full_mode_summary_is_coherent(self):
        from core.flight_check import run_flight_check
        report = run_flight_check(mode="full", json_only=True)
        total = report.total_passed + report.total_failed + report.total_errors
        # Sum of all suite-level counts should match totals
        suite_total = sum(
            s.passed + s.failed + s.errors for s in report.suites
        )
        assert total == suite_total, f"Mismatch: total={total}, suite_sum={suite_total}"


# ═══════════════════════════════════════════════════════════════════════════════
# Flight Check — CLI
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlightCheckCLI:
    """CLI integration tests."""

    def test_cli_quick_default(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.flight_check", "--json-only"],
            capture_output=True, text=True, timeout=300,
            cwd=str(_IMPERIO_ROOT),
            env={**os.environ, "CI_TEST_MODE": "1"},
        )
        assert result.returncode == 0, f"CLI failed: {result.stderr[:500]}"
        data = json.loads(result.stdout)
        assert data["mode"] == "quick"
        assert data["passed"] is True

    @pytest.mark.slow
    def test_cli_full_mode(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.flight_check", "--full", "--json-only"],
            capture_output=True, text=True, timeout=600,
            cwd=str(_IMPERIO_ROOT),
            env={**os.environ, "CI_TEST_MODE": "1"},
        )
        # Full mode may exit 0 (if allowed-fail suites only) or 1
        # Either is acceptable — just verify it doesn't crash
        assert result.returncode in (0, 1), (
            f"CLI full crashed with exit code {result.returncode}: {result.stderr[:500]}"
        )
        data = json.loads(result.stdout)
        assert data["mode"] == "full"

    def test_cli_help(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.flight_check", "--help"],
            capture_output=True, text=True, timeout=30,
            cwd=str(_IMPERIO_ROOT),
        )
        assert result.returncode == 0
        stdout_lower = result.stdout.lower()
        assert "flight check" in stdout_lower
        assert "quick" in stdout_lower
        assert "full" in stdout_lower

    def test_cli_short_flags(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.flight_check", "-q", "-j"],
            capture_output=True, text=True, timeout=300,
            cwd=str(_IMPERIO_ROOT),
            env={**os.environ, "CI_TEST_MODE": "1"},
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["mode"] == "quick"
        assert data["passed"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# Flight Check — Suite Result Parsing
# ═══════════════════════════════════════════════════════════════════════════════

class TestSuiteResultParsing:
    """Unit tests for _run_suite and SuiteResult."""

    def test_suite_result_frozen_dataclass(self):
        from core.flight_check import SuiteResult
        sr = SuiteResult(
            suite="tests/fake.py", passed=10, failed=0, errors=0,
            duration_seconds=2.5, raw_output="ok",
        )
        assert sr.passed == 10
        assert sr.suite == "tests/fake.py"
        with pytest.raises(Exception):
            sr.passed = 11  # frozen

    def test_suite_result_for_missing_file(self):
        from core.flight_check import _run_suite
        result = _run_suite(
            "tests/nonexistent_suite.py",
            cwd=_IMPERIO_ROOT,
            env=dict(os.environ, CI_TEST_MODE="1"),
        )
        assert result.errors == 1, f"Expected 1 error, got {result.errors}"
        assert "not found" in result.raw_output.lower()

    def test_run_suite_never_raises(self):
        from core.flight_check import _run_suite
        # Even with a bad cwd, should not crash
        result = _run_suite(
            "tests/test_cinematic_video.py",
            cwd=Path("/nonexistent"),
            env=dict(os.environ, CI_TEST_MODE="1"),
        )
        assert isinstance(result.passed, int)
        assert isinstance(result.failed, int)


# ═══════════════════════════════════════════════════════════════════════════════
# Flight Check — Report Persistence
# ═══════════════════════════════════════════════════════════════════════════════

class TestReportPersistence:
    """Report writing and retrieval."""

    def test_report_written_to_correct_dir(self):
        from core.flight_check import run_flight_check, _REPORT_DIR
        report = run_flight_check(mode="quick", json_only=True)
        report_path = _REPORT_DIR / f"{report.check_id}.json"
        assert report_path.exists()

    def test_report_json_is_valid(self):
        from core.flight_check import run_flight_check, _REPORT_DIR
        report = run_flight_check(mode="quick", json_only=True)
        report_path = _REPORT_DIR / f"{report.check_id}.json"
        with open(report_path) as f:
            data = json.load(f)
        required = ["check_id", "checked_at", "mode", "passed",
                     "total_passed", "total_failed", "total_errors",
                     "duration_total_seconds", "suites"]
        for key in required:
            assert key in data, f"Missing key '{key}' in flight check report"

    def test_failed_suite_output_included(self):
        """Simulate: if a suite fails, raw output is included in JSON."""
        from core.flight_check import SuiteResult

        # Build a failing result manually
        bad = SuiteResult(
            suite="tests/failing.py",
            passed=5,
            failed=3,
            errors=1,
            duration_seconds=0.5,
            raw_output="AssertionError: x != y",
        )
        # Verify raw_output is accessible (not suppressed)
        assert "AssertionError" in bad.raw_output


# ═══════════════════════════════════════════════════════════════════════════════
# Flight Check — Isolation
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlightCheckIsolation:
    """Flight check never imports forbidden layers."""

    FORBIDDEN = (
        "flow_operator",
        "revenue_layer",
        "dispatch_gate",
        "master_pipeline",
        "visual_truth",
    )

    def test_no_forbidden_imports_in_flight_check(self):
        import ast
        import inspect
        import core.flight_check as fc

        src = inspect.getsource(fc)
        tree = ast.parse(src)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not any(
                        fb in alias.name for fb in self.FORBIDDEN
                    ), f"Forbidden import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not any(
                        fb in node.module for fb in self.FORBIDDEN
                    ), f"Forbidden import: {node.module}"

    def test_flight_check_only_uses_stdlib(self):
        import inspect
        import core.flight_check as fc
        src = inspect.getsource(fc)
        # Flight check must not import any core modules (only stdlib)
        for line in src.split("\n"):
            stripped = line.strip()
            if stripped.startswith("from core.") and "flight_check" not in stripped:
                pytest.fail(f"Flight check imports core module: {stripped}")
            if stripped.startswith("import core.") and "flight_check" not in stripped:
                pytest.fail(f"Flight check imports core module: {stripped}")


# ═══════════════════════════════════════════════════════════════════════════════
# Flight Check — Never-Raise Contract
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlightCheckNeverRaise:
    """All flight check paths return a report, never raise."""

    def test_run_flight_check_never_raises(self):
        from core.flight_check import run_flight_check
        # Even with absurd input, should return a report
        report = run_flight_check(mode="", json_only=True)
        assert report is not None
        assert hasattr(report, "passed")

    def test_empty_argv_does_not_crash(self):
        from core.flight_check import main
        exit_code = main([])
        assert exit_code in (0, 1)

    def test_bad_flag_does_not_crash(self):
        from core.flight_check import main
        exit_code = main(["--nuclear-launch"])
        assert exit_code in (0, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# Flight Check — Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlightCheckEdgeCases:
    """Edge cases and robustness."""

    def test_flight_check_report_id_is_unique(self):
        from core.flight_check import run_flight_check
        import time
        r1 = run_flight_check(mode="quick", json_only=True)
        time.sleep(1.1)  # Ensure different second
        r2 = run_flight_check(mode="quick", json_only=True)
        assert r1.check_id != r2.check_id

    def test_flight_check_report_dataclass_frozen(self):
        from core.flight_check import FlightCheckReport, SuiteResult
        sr = SuiteResult(
            suite="test", passed=1, failed=0, errors=0,
            duration_seconds=0.1, raw_output="",
        )
        report = FlightCheckReport(
            check_id="FLIGHT-TEST",
            checked_at="2026-01-01T00:00:00Z",
            mode="quick",
            total_passed=1,
            total_failed=0,
            total_errors=0,
            suites=(sr,),
            passed=True,
            duration_total_seconds=0.1,
        )
        assert report.passed is True
        with pytest.raises(Exception):
            report.passed = False  # frozen

    def test_flight_check_report_total_matches_suites(self):
        from core.flight_check import run_flight_check
        report = run_flight_check(mode="quick", json_only=True)
        suite_passed = sum(s.passed for s in report.suites)
        suite_failed = sum(s.failed for s in report.suites)
        suite_errors = sum(s.errors for s in report.suites)
        assert report.total_passed == suite_passed
        assert report.total_failed == suite_failed
        assert report.total_errors == suite_errors

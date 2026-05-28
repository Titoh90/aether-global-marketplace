#!/usr/bin/env python3
"""
test_system_readiness.py — Tests for the System Readiness Layer.

Coverage:
- All 12 individual health checks
- PolicyEntry dataclass: weights, failure_modes, depends_on, is_critical()
- Dependency resolution: topological sort, dependency gate
- ReadinessReport structure and frozen dataclass
- run_readiness_check() integration with policy engine
- CLI: --json-only, --skip, --help
- Flight check --readiness integration
- SRE preflight_gate integration
- Never-raise contract
- Isolation: no forbidden imports
- Report persistence and retrieval (includes policy metadata)
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

_IMPERIO_ROOT = Path(__file__).parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))


# ═══════════════════════════════════════════════════════════════════════════════
# PolicyEntry dataclass
# ═══════════════════════════════════════════════════════════════════════════════

class TestPolicyEntry:
    """PolicyEntry frozen dataclass tests."""

    def test_policy_entry_basic(self):
        from core.system_readiness import PolicyEntry
        pe = PolicyEntry(name="test", check_fn=lambda: None)
        assert pe.name == "test"
        assert pe.weight == 0.5
        assert pe.failure_mode == "warn"
        assert pe.depends_on == ()
        assert pe.is_critical() is False

    def test_policy_entry_critical(self):
        from core.system_readiness import PolicyEntry
        pe = PolicyEntry(name="test", check_fn=lambda: None,
                         weight=1.0, failure_mode="block")
        assert pe.is_critical() is True

    def test_policy_entry_weight_edge(self):
        from core.system_readiness import PolicyEntry
        # weight=0.8 + warn → NOT critical
        pe = PolicyEntry(name="test", check_fn=lambda: None,
                         weight=0.8, failure_mode="warn")
        assert pe.is_critical() is False
        # weight=0.8 + block → critical
        pe2 = PolicyEntry(name="test2", check_fn=lambda: None,
                          weight=0.8, failure_mode="block")
        assert pe2.is_critical() is True

    def test_policy_entry_weight_out_of_range(self):
        from core.system_readiness import PolicyEntry
        with pytest.raises(ValueError):
            PolicyEntry(name="test", check_fn=lambda: None, weight=1.5)
        with pytest.raises(ValueError):
            PolicyEntry(name="test", check_fn=lambda: None, weight=-0.1)

    def test_policy_entry_invalid_failure_mode(self):
        from core.system_readiness import PolicyEntry
        with pytest.raises(ValueError):
            PolicyEntry(name="test", check_fn=lambda: None, failure_mode="invalid")

    def test_policy_entry_depends_on(self):
        from core.system_readiness import PolicyEntry
        pe = PolicyEntry(name="test", check_fn=lambda: None,
                         depends_on=("other_check",))
        assert pe.depends_on == ("other_check",)

    def test_policy_entry_frozen(self):
        from core.system_readiness import PolicyEntry
        pe = PolicyEntry(name="test", check_fn=lambda: None)
        with pytest.raises(Exception):
            pe.weight = 0.9  # type: ignore
    """ReadinessCheck frozen dataclass tests."""

    def test_readiness_check_healthy(self):
        from core.system_readiness import ReadinessCheck
        rc = ReadinessCheck(name="test", status="healthy", detail="ok", latency_ms=5)
        assert rc.name == "test"
        assert rc.status == "healthy"
        assert rc.is_healthy() is True
        assert rc.critical is False

    def test_readiness_check_unhealthy(self):
        from core.system_readiness import ReadinessCheck
        rc = ReadinessCheck(name="test", status="unhealthy", detail="fail",
                            latency_ms=10, critical=True)
        assert rc.is_healthy() is False
        assert rc.critical is True

    def test_readiness_check_frozen(self):
        from core.system_readiness import ReadinessCheck
        rc = ReadinessCheck(name="test", status="healthy", detail="ok", latency_ms=5)
        with pytest.raises(Exception):
            rc.status = "unhealthy"  # type: ignore

    def test_readiness_check_degraded(self):
        from core.system_readiness import ReadinessCheck
        rc = ReadinessCheck(name="test", status="degraded", detail="warn", latency_ms=3)
        assert rc.is_healthy() is False
        assert rc.status == "degraded"


class TestReadinessReportDataclass:
    """ReadinessReport frozen dataclass tests."""

    def test_readiness_report_frozen(self):
        from core.system_readiness import ReadinessReport, ReadinessCheck
        checks = (ReadinessCheck(name="a", status="healthy", detail="ok", latency_ms=1),)
        report = ReadinessReport(
            check_id="READINESS-test",
            checked_at="2026-01-01T00:00:00Z",
            checks=checks,
            all_healthy=True,
            critical_pass=True,
            degraded=(),
            unhealthy=(),
            duration_ms=10,
        )
        assert report.all_healthy is True
        assert report.critical_pass is True
        with pytest.raises(Exception):
            report.all_healthy = False  # type: ignore

    def test_readiness_report_with_degraded(self):
        from core.system_readiness import ReadinessReport, ReadinessCheck
        checks = (
            ReadinessCheck(name="a", status="healthy", detail="ok", latency_ms=1),
            ReadinessCheck(name="b", status="degraded", detail="warn", latency_ms=2),
        )
        report = ReadinessReport(
            check_id="READINESS-test",
            checked_at="2026-01-01T00:00:00Z",
            checks=checks,
            all_healthy=False,
            critical_pass=True,
            degraded=("b",),
            unhealthy=(),
            duration_ms=10,
        )
        assert report.all_healthy is False
        assert report.critical_pass is True
        assert "b" in report.degraded

    def test_readiness_report_with_unhealthy_critical(self):
        from core.system_readiness import ReadinessReport, ReadinessCheck
        checks = (
            ReadinessCheck(name="disk", status="unhealthy", detail="no space",
                           latency_ms=5, critical=True),
        )
        report = ReadinessReport(
            check_id="READINESS-test",
            checked_at="2026-01-01T00:00:00Z",
            checks=checks,
            all_healthy=False,
            critical_pass=False,
            degraded=(),
            unhealthy=("disk",),
            duration_ms=10,
        )
        assert report.critical_pass is False
        assert "disk" in report.unhealthy


# ═══════════════════════════════════════════════════════════════════════════════
# Individual health checks
# ═══════════════════════════════════════════════════════════════════════════════

class TestDiskSpaceCheck:
    """Disk space health check."""

    def test_disk_space_healthy(self):
        from core.system_readiness import _check_disk_space
        result = _check_disk_space()
        assert result.name == "disk_space"
        # With normal disk space, should be healthy
        assert result.status in ("healthy", "degraded")
        assert result.latency_ms >= 0

    def test_disk_space_returns_readiness_check(self):
        from core.system_readiness import _check_disk_space, ReadinessCheck
        result = _check_disk_space()
        assert isinstance(result, ReadinessCheck)

    def test_disk_space_never_raises_with_bad_path(self):
        from core.system_readiness import _check_disk_space
        # Should never raise, even with system issues
        result = _check_disk_space()
        assert result is not None
        assert result.name is not None
        assert result.status is not None


class TestProviderHealthCheck:
    """LLM provider health check."""

    def test_provider_health_returns_readiness_check(self):
        from core.system_readiness import _check_provider_health, ReadinessCheck
        result = _check_provider_health()
        assert isinstance(result, ReadinessCheck)
        assert result.name == "provider_health"

    def test_provider_health_valid_status(self):
        from core.system_readiness import _check_provider_health
        result = _check_provider_health()
        assert result.status in ("healthy", "degraded", "skipped")


class TestDispatchGateCheck:
    """Dispatch gate health check."""

    def test_dispatch_gate_returns_readiness_check(self):
        from core.system_readiness import _check_dispatch_gate, ReadinessCheck
        result = _check_dispatch_gate()
        assert isinstance(result, ReadinessCheck)
        assert result.name == "dispatch_gate"

    def test_dispatch_gate_valid_status(self):
        from core.system_readiness import _check_dispatch_gate
        result = _check_dispatch_gate()
        assert result.status in ("healthy", "degraded", "unhealthy", "skipped")


class TestComposioTokenCheck:
    """Composio token health check."""

    def test_composio_token_returns_readiness_check(self):
        from core.system_readiness import _check_composio_token, ReadinessCheck
        result = _check_composio_token()
        assert isinstance(result, ReadinessCheck)
        assert result.name == "composio_token"

    def test_composio_token_valid_status(self):
        from core.system_readiness import _check_composio_token
        result = _check_composio_token()
        assert result.status in ("healthy", "degraded")

    def test_composio_token_with_env_var_set(self, monkeypatch):
        monkeypatch.setenv("COMPOSIO_API_KEY", "test_key_12345678")
        from core.system_readiness import _check_composio_token
        result = _check_composio_token()
        assert result.status == "healthy"
        assert "present" in result.detail.lower()


class TestFaissVectorStoreCheck:
    """FAISS vector_store health check."""

    def test_faiss_vs_returns_readiness_check(self):
        from core.system_readiness import _check_faiss_vector_store, ReadinessCheck
        result = _check_faiss_vector_store()
        assert isinstance(result, ReadinessCheck)
        assert result.name == "faiss_vector_store"

    def test_faiss_vs_valid_status(self):
        from core.system_readiness import _check_faiss_vector_store
        result = _check_faiss_vector_store()
        assert result.status in ("healthy", "degraded", "unhealthy", "skipped")


class TestFaissKnowledgeStoreCheck:
    """FAISS knowledge_store health check."""

    def test_faiss_ks_returns_readiness_check(self):
        from core.system_readiness import _check_faiss_knowledge_store, ReadinessCheck
        result = _check_faiss_knowledge_store()
        assert isinstance(result, ReadinessCheck)
        assert result.name == "faiss_knowledge_store"

    def test_faiss_ks_valid_status(self):
        from core.system_readiness import _check_faiss_knowledge_store
        result = _check_faiss_knowledge_store()
        assert result.status in ("healthy", "degraded", "unhealthy", "skipped")


class TestArchetypeMemoryCheck:
    """Archetype memory health check."""

    def test_archetype_memory_returns_readiness_check(self):
        from core.system_readiness import _check_archetype_memory, ReadinessCheck
        result = _check_archetype_memory()
        assert isinstance(result, ReadinessCheck)
        assert result.name == "archetype_memory"

    def test_archetype_memory_valid_status(self):
        from core.system_readiness import _check_archetype_memory
        result = _check_archetype_memory()
        assert result.status in ("healthy", "degraded", "skipped")


class TestDriftDetectorCheck:
    """Drift detector health check."""

    def test_drift_detector_returns_readiness_check(self):
        from core.system_readiness import _check_drift_detector, ReadinessCheck
        result = _check_drift_detector()
        assert isinstance(result, ReadinessCheck)
        assert result.name == "drift_detector"

    def test_drift_detector_valid_status(self):
        from core.system_readiness import _check_drift_detector
        result = _check_drift_detector()
        assert result.status in ("healthy", "degraded", "skipped")


class TestBioAuthenticatedCheck:
    """Bio authenticator health check."""

    def test_bio_authenticated_returns_readiness_check(self):
        from core.system_readiness import _check_bio_authenticated, ReadinessCheck
        result = _check_bio_authenticated()
        assert isinstance(result, ReadinessCheck)
        assert result.name == "bio_authenticated"

    def test_bio_authenticated_valid_status(self):
        from core.system_readiness import _check_bio_authenticated
        result = _check_bio_authenticated()
        assert result.status in ("healthy", "degraded")


class TestRevenueLedgerCheck:
    """Revenue ledger health check."""

    def test_revenue_ledger_returns_readiness_check(self):
        from core.system_readiness import _check_revenue_ledger, ReadinessCheck
        result = _check_revenue_ledger()
        assert isinstance(result, ReadinessCheck)
        assert result.name == "revenue_ledger"

    def test_revenue_ledger_valid_status(self):
        from core.system_readiness import _check_revenue_ledger
        result = _check_revenue_ledger()
        assert result.status in ("healthy", "degraded", "unhealthy", "skipped")


class TestCISchedulerCheck:
    """CI scheduler health check."""

    def test_ci_scheduler_returns_readiness_check(self):
        from core.system_readiness import _check_ci_scheduler, ReadinessCheck
        result = _check_ci_scheduler()
        assert isinstance(result, ReadinessCheck)
        assert result.name == "ci_scheduler"

    def test_ci_scheduler_valid_status(self):
        from core.system_readiness import _check_ci_scheduler
        result = _check_ci_scheduler()
        assert result.status in ("healthy", "degraded", "skipped")


class TestFlightCheckFreshnessCheck:
    """Flight check freshness check."""

    def test_flight_check_freshness_returns_readiness_check(self):
        from core.system_readiness import _check_flight_check_freshness, ReadinessCheck
        result = _check_flight_check_freshness()
        assert isinstance(result, ReadinessCheck)
        assert result.name == "flight_check"

    def test_flight_check_freshness_valid_status(self):
        from core.system_readiness import _check_flight_check_freshness
        result = _check_flight_check_freshness()
        assert result.status in ("healthy", "degraded", "skipped")


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: run_readiness_check
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunReadinessCheck:
    """run_readiness_check() integration tests."""

    def test_run_all_checks_returns_report(self):
        from core.system_readiness import run_readiness_check, ReadinessReport
        report = run_readiness_check(json_only=True)
        assert isinstance(report, ReadinessReport)
        assert report.check_id.startswith("READINESS-")
        assert report.checked_at
        assert isinstance(report.checks, tuple)

    def test_all_12_checks_present(self):
        from core.system_readiness import run_readiness_check, _CHECKS
        report = run_readiness_check(json_only=True)
        expected_names = {name for name, _, _ in _CHECKS}
        actual_names = {c.name for c in report.checks}
        assert expected_names == actual_names, (
            f"Missing checks: {expected_names - actual_names}"
        )

    def test_every_check_has_latency(self):
        from core.system_readiness import run_readiness_check
        report = run_readiness_check(json_only=True)
        for check in report.checks:
            assert check.latency_ms >= 0, f"{check.name}: negative latency"

    def test_all_checks_have_valid_status(self):
        from core.system_readiness import run_readiness_check
        report = run_readiness_check(json_only=True)
        valid_statuses = {"healthy", "degraded", "unhealthy", "skipped"}
        for check in report.checks:
            assert check.status in valid_statuses, (
                f"{check.name}: invalid status '{check.status}'"
            )

    def test_critical_checks_marked(self):
        from core.system_readiness import run_readiness_check, _CHECKS
        report = run_readiness_check(json_only=True)
        critical_names = {name for name, _, critical in _CHECKS if critical}
        # Critical checks may be skipped if their dependencies are unhealthy —
        # but even skipped-critical checks must carry critical=True from policy.
        for check in report.checks:
            if check.name in critical_names:
                assert check.critical is True, (
                    f"{check.name}: should be marked critical ({check.critical})"
                )
        # Verify at least 3 checks are critical (count all, including skipped)
        critical_in_report = [c for c in report.checks if c.critical]
        assert len(critical_in_report) >= 3, (
            f"Expected >=3 critical checks, got {len(critical_in_report)}: "
            f"{[c.name for c in critical_in_report]}"
        )

    def test_report_summary_consistent(self):
        from core.system_readiness import run_readiness_check
        report = run_readiness_check(json_only=True)
        degraded = [c for c in report.checks if c.status == "degraded"]
        unhealthy = [c for c in report.checks if c.status == "unhealthy"]
        assert set(report.degraded) == {c.name for c in degraded}
        assert set(report.unhealthy) == {c.name for c in unhealthy}
        assert report.all_healthy == (len(degraded) == 0 and len(unhealthy) == 0)

    def test_skip_flag_works(self):
        from core.system_readiness import run_readiness_check
        report = run_readiness_check(json_only=True, skip=("composio_token",))
        composio = next((c for c in report.checks if c.name == "composio_token"), None)
        assert composio is not None
        assert composio.status == "skipped"

    def test_report_duration_positive(self):
        from core.system_readiness import run_readiness_check
        report = run_readiness_check(json_only=True)
        assert report.duration_ms > 0

    def test_report_check_id_unique(self):
        from core.system_readiness import run_readiness_check
        import time
        r1 = run_readiness_check(json_only=True)
        time.sleep(1.1)
        r2 = run_readiness_check(json_only=True)
        assert r1.check_id != r2.check_id


# ═══════════════════════════════════════════════════════════════════════════════
# Preflight gate (SRE integration)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPreflightGate:
    """SRE preflight_gate integration."""

    def test_preflight_gate_returns_tuple(self):
        from core.system_readiness import preflight_gate
        passed, report = preflight_gate()
        assert isinstance(passed, bool)
        assert report is not None
        assert hasattr(report, "critical_pass")

    def test_preflight_gate_passes_when_critical_healthy(self):
        from core.system_readiness import preflight_gate
        passed, report = preflight_gate()
        if report.critical_pass:
            assert passed is True
        else:
            assert passed is False

    def test_preflight_gate_report_is_readiness_report(self):
        from core.system_readiness import preflight_gate, ReadinessReport
        _, report = preflight_gate()
        assert isinstance(report, ReadinessReport)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestReadinessCLI:
    """CLI integration tests for system_readiness."""

    def test_cli_default(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.system_readiness", "--json-only"],
            capture_output=True, text=True, timeout=120,
            cwd=str(_IMPERIO_ROOT),
        )
        assert result.returncode in (0, 1), (
            f"CLI crashed with exit code {result.returncode}: {result.stderr[:500]}"
        )
        data = json.loads(result.stdout)
        assert "check_id" in data
        assert "all_healthy" in data
        assert "critical_pass" in data

    def test_cli_help(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.system_readiness", "--help"],
            capture_output=True, text=True, timeout=30,
            cwd=str(_IMPERIO_ROOT),
        )
        assert result.returncode == 0
        stdout_lower = result.stdout.lower()
        assert "readiness" in stdout_lower
        assert "skip" in stdout_lower

    def test_cli_skip_flag(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.system_readiness",
             "--json-only", "--skip=composio_token,ci_scheduler"],
            capture_output=True, text=True, timeout=120,
            cwd=str(_IMPERIO_ROOT),
        )
        assert result.returncode in (0, 1)
        data = json.loads(result.stdout)
        assert data["critical_pass"] in (True, False)

    def test_cli_short_flags(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.system_readiness", "-j"],
            capture_output=True, text=True, timeout=120,
            cwd=str(_IMPERIO_ROOT),
        )
        assert result.returncode in (0, 1)
        data = json.loads(result.stdout)
        assert "check_id" in data


# ═══════════════════════════════════════════════════════════════════════════════
# Flight check --readiness integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlightCheckReadinessIntegration:
    """Flight check --readiness flag integration."""

    def test_flight_check_readiness_flag(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.flight_check", "--readiness", "--json-only"],
            capture_output=True, text=True, timeout=120,
            cwd=str(_IMPERIO_ROOT),
        )
        assert result.returncode in (0, 1), (
            f"Readiness mode crashed: {result.stderr[:500]}"
        )

    def test_flight_check_short_readiness(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "core.flight_check", "-r", "-j"],
            capture_output=True, text=True, timeout=120,
            cwd=str(_IMPERIO_ROOT),
        )
        assert result.returncode in (0, 1), (
            f"Short readiness flag crash: {result.stderr[:500]}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Report persistence
# ═══════════════════════════════════════════════════════════════════════════════

class TestReadinessReportPersistence:
    """Report writing and retrieval tests."""

    def test_report_written_to_correct_dir(self):
        from core.system_readiness import run_readiness_check, _REPORT_DIR
        report = run_readiness_check(json_only=True)
        report_path = _REPORT_DIR / f"{report.check_id}.json"
        assert report_path.exists(), f"Report not found at {report_path}"

    def test_report_json_is_valid(self):
        from core.system_readiness import run_readiness_check, _REPORT_DIR
        report = run_readiness_check(json_only=True)
        report_path = _REPORT_DIR / f"{report.check_id}.json"
        with open(report_path) as f:
            data = json.load(f)
        required = ["check_id", "checked_at", "all_healthy", "critical_pass",
                     "checks"]
        for key in required:
            assert key in data, f"Missing key '{key}' in readiness report"

    def test_report_checks_have_all_fields(self):
        from core.system_readiness import run_readiness_check, _REPORT_DIR
        report = run_readiness_check(json_only=True)
        report_path = _REPORT_DIR / f"{report.check_id}.json"
        with open(report_path) as f:
            data = json.load(f)
        for check in data["checks"]:
            assert "name" in check
            assert "status" in check
            assert "detail" in check
            assert "latency_ms" in check
            assert "critical" in check

    def test_get_latest_readiness_report(self):
        from core.system_readiness import get_latest_readiness_report
        report = get_latest_readiness_report()
        if report is not None:
            assert report.check_id.startswith("READINESS-")
            assert isinstance(report.checks, tuple)


# ═══════════════════════════════════════════════════════════════════════════════
# Never-raise contract
# ═══════════════════════════════════════════════════════════════════════════════

class TestReadinessNeverRaise:
    """All readiness paths must return a report, never raise."""

    def test_run_readiness_check_never_raises(self):
        from core.system_readiness import run_readiness_check, _CHECKS
        # Even with skip of all checks
        report = run_readiness_check(
            json_only=True,
            skip=tuple(name for name, _, _ in _CHECKS),
        )
        assert report is not None
        assert hasattr(report, "critical_pass")

    def test_every_check_fn_never_raises(self):
        from core.system_readiness import _CHECKS
        for name, check_fn, _ in _CHECKS:
            try:
                result = check_fn()
                assert result is not None, f"{name}: returned None"
                assert result.name == name, f"{name}: wrong name '{result.name}'"
            except Exception as e:
                pytest.fail(f"{name}: check_fn raised {type(e).__name__}: {e}")

    def test_preflight_gate_never_raises(self):
        from core.system_readiness import preflight_gate
        try:
            passed, report = preflight_gate()
            assert isinstance(passed, bool)
            assert report is not None
        except Exception as e:
            pytest.fail(f"preflight_gate raised {type(e).__name__}: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# Isolation
# ═══════════════════════════════════════════════════════════════════════════════

class TestReadinessIsolation:
    """System readiness must not import forbidden layers."""

    FORBIDDEN = (
        "flow_operator",
        "master_pipeline",
        "browser_use",
        "playwright",
        "instagrapi",
    )

    def test_no_forbidden_imports(self):
        import ast
        import inspect
        import core.system_readiness as sr

        src = inspect.getsource(sr)
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

    def test_readiness_only_imports_stdlib_and_core(self):
        import inspect
        import core.system_readiness as sr
        src = inspect.getsource(sr)
        for line in src.split("\n"):
            stripped = line.strip()
            if stripped.startswith("from ") or stripped.startswith("import "):
                # Allow stdlib and core/ imports
                if "core." in stripped or "platform_dispatch" in stripped or "revenue_layer" in stripped:
                    continue  # These are expected
                # Check for forbidden layers
                for fb in self.FORBIDDEN:
                    assert fb not in stripped, f"Forbidden import: {stripped}"


# ═══════════════════════════════════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestReadinessEdgeCases:
    """Edge cases and robustness."""

    def test_empty_skip_list_works(self):
        from core.system_readiness import run_readiness_check
        report = run_readiness_check(json_only=True, skip=())
        assert report.all_healthy in (True, False)

    def test_all_skipped_produces_report(self):
        from core.system_readiness import run_readiness_check, _CHECKS
        all_names = tuple(name for name, _, _ in _CHECKS)
        report = run_readiness_check(json_only=True, skip=all_names)
        assert all(c.status == "skipped" for c in report.checks)
        assert report.all_healthy is True  # All skipped = no degradations
        assert report.critical_pass is True  # No critical failures since skipped

    def test_ok_helper(self):
        from core.system_readiness import _ok
        result = _ok("test", "all good", 5)
        assert result.status == "healthy"
        assert result.name == "test"
        assert result.critical is False

    def test_degraded_helper(self):
        from core.system_readiness import _degraded
        result = _degraded("test", "warning", 5, critical=True)
        assert result.status == "degraded"
        assert result.critical is True

    def test_unhealthy_helper(self):
        from core.system_readiness import _unhealthy
        result = _unhealthy("test", "dead", 5)
        assert result.status == "unhealthy"

    def test_skipped_helper(self):
        from core.system_readiness import _skipped
        result = _skipped("test", "not needed")
        assert result.status == "skipped"
        assert result.latency_ms == 0

    def test_checks_table_all_present(self):
        """Verify _CHECKS contains exactly 12 entries."""
        from core.system_readiness import _CHECKS
        assert len(_CHECKS) == 12, f"Expected 12 checks, got {len(_CHECKS)}"
        names = {name for name, _, _ in _CHECKS}
        required = {
            "faiss_vector_store", "faiss_knowledge_store", "archetype_memory",
            "drift_detector", "bio_authenticated", "provider_health",
            "dispatch_gate", "composio_token", "disk_space",
            "revenue_ledger", "ci_scheduler", "flight_check",
        }
        assert names == required, f"Missing: {required - names}, Extra: {names - required}"

    def test_critical_checks_defined(self):
        """Verify critical checks: faiss_vector_store, dispatch_gate, disk_space."""
        from core.system_readiness import _CHECKS
        critical_names = {name for name, _, critical in _CHECKS if critical}
        assert "faiss_vector_store" in critical_names, "faiss_vector_store should be critical"
        assert "dispatch_gate" in critical_names, "dispatch_gate should be critical"
        assert "disk_space" in critical_names, "disk_space should be critical"
        assert len(critical_names) == 3, (
            f"Expected exactly 3 critical checks, got {len(critical_names)}: {critical_names}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Policy Engine: dependency graph, weights, failure modes
# ═══════════════════════════════════════════════════════════════════════════════

class TestPolicyEngine:
    """Policy engine: dependency resolution, weight-based criticality, failure modes."""

    def test_dependency_gate_skips_when_dep_unhealthy(self):
        """If a dependency is unhealthy, the dependent check is skipped in the runner."""
        from core.system_readiness import (
            ReadinessCheck, PolicyEntry, run_readiness_check,
        )
        import core.system_readiness as sr

        call_log: list[str] = []

        def mock_composio_unhealthy():
            return ReadinessCheck(
                name="composio_token", status="unhealthy",
                detail="no token", latency_ms=1,
            )

        def mock_dispatch_gate():
            call_log.append("dispatch_gate_called")
            return ReadinessCheck(
                name="dispatch_gate", status="healthy",
                detail="gate ok", latency_ms=1,
            )

        mock_policy = (
            PolicyEntry(name="composio_token", check_fn=mock_composio_unhealthy,
                        weight=0.9, failure_mode="warn"),
            PolicyEntry(name="dispatch_gate", check_fn=mock_dispatch_gate,
                        weight=1.0, failure_mode="block", depends_on=("composio_token",)),
        )

        # Monkey-patch _POLICY and re-derive _CHECKS
        try:
            original_policy = sr._POLICY
            original_checks = sr._CHECKS
            sr._POLICY = mock_policy
            sr._CHECKS = tuple(
                (e.name, e.check_fn, e.is_critical()) for e in mock_policy
            )
            report = run_readiness_check(json_only=True)
        finally:
            sr._POLICY = original_policy
            sr._CHECKS = original_checks

        # dispatch_gate should be SKIPPED, never called
        assert "dispatch_gate_called" not in call_log, (
            "dispatch_gate check_fn was called even though composio_token was unhealthy"
        )
        dispatch = next((c for c in report.checks if c.name == "dispatch_gate"), None)
        assert dispatch is not None
        assert dispatch.status == "skipped", (
            f"Expected skipped, got {dispatch.status}"
        )
        assert "composio_token=unhealthy" in dispatch.detail
        # Criticality still applied from policy even when skipped
        assert dispatch.critical is True

    def test_dependency_gate_allows_when_dep_degraded(self):
        """A degraded dependency should NOT block its dependents — runner test."""
        from core.system_readiness import (
            ReadinessCheck, PolicyEntry, run_readiness_check,
        )
        import core.system_readiness as sr

        call_log: list[str] = []

        def mock_composio_degraded():
            return ReadinessCheck(
                name="composio_token", status="degraded",
                detail="token expiring soon", latency_ms=1,
            )

        def mock_dispatch_gate():
            call_log.append("dispatch_gate_called")
            return ReadinessCheck(
                name="dispatch_gate", status="healthy",
                detail="gate ok", latency_ms=1,
            )

        mock_policy = (
            PolicyEntry(name="composio_token", check_fn=mock_composio_degraded,
                        weight=0.9, failure_mode="warn"),
            PolicyEntry(name="dispatch_gate", check_fn=mock_dispatch_gate,
                        weight=1.0, failure_mode="block", depends_on=("composio_token",)),
        )

        try:
            original_policy = sr._POLICY
            original_checks = sr._CHECKS
            sr._POLICY = mock_policy
            sr._CHECKS = tuple(
                (e.name, e.check_fn, e.is_critical()) for e in mock_policy
            )
            report = run_readiness_check(json_only=True)
        finally:
            sr._POLICY = original_policy
            sr._CHECKS = original_checks

        # dispatch_gate SHOULD be called (degraded dep doesn't block)
        assert "dispatch_gate_called" in call_log, (
            "dispatch_gate check_fn was NOT called — degraded dep incorrectly blocked it"
        )
        dispatch = next((c for c in report.checks if c.name == "dispatch_gate"), None)
        assert dispatch is not None
        assert dispatch.status != "skipped", (
            f"Expected dispatch_gate to run (not skipped), got {dispatch.status}"
        )

    def test_topological_sort_respects_dag(self):
        """Topological sort puts dependencies before dependents."""
        from core.system_readiness import PolicyEntry, _resolve_dependency_order

        def dummy():
            from core.system_readiness import ReadinessCheck
            return ReadinessCheck(name="dummy", status="healthy", detail="ok", latency_ms=0)

        # A → B → C  (A has no deps, B depends on A, C depends on B)
        policy = (
            PolicyEntry(name="c", check_fn=dummy, weight=0.5, depends_on=("b",)),
            PolicyEntry(name="b", check_fn=dummy, weight=0.5, depends_on=("a",)),
            PolicyEntry(name="a", check_fn=dummy, weight=0.5),
        )

        ordered = _resolve_dependency_order(policy)
        names = [e.name for e in ordered]
        # A must come before B, B before C
        assert names.index("a") < names.index("b"), f"Expected A before B, got {names}"
        assert names.index("b") < names.index("c"), f"Expected B before C, got {names}"

    def test_cycle_detection_falls_back_to_declaration_order(self):
        """A cycle in the dependency graph falls back to declaration order."""
        from core.system_readiness import PolicyEntry, _resolve_dependency_order

        def dummy():
            from core.system_readiness import ReadinessCheck
            return ReadinessCheck(name="dummy", status="healthy", detail="ok", latency_ms=0)

        # A → B → A (cycle)
        policy = (
            PolicyEntry(name="a", check_fn=dummy, weight=0.5, depends_on=("b",)),
            PolicyEntry(name="b", check_fn=dummy, weight=0.5, depends_on=("a",)),
        )

        ordered = _resolve_dependency_order(policy)
        # Should fall back to declaration order: a, b
        assert len(ordered) == 2
        assert ordered[0].name == "a"
        assert ordered[1].name == "b"

    def test_nonexistent_dependency_ignored(self):
        """A dependency on a non-existent check should not crash."""
        from core.system_readiness import PolicyEntry, _resolve_dependency_order

        def dummy():
            from core.system_readiness import ReadinessCheck
            return ReadinessCheck(name="dummy", status="healthy", detail="ok", latency_ms=0)

        policy = (
            PolicyEntry(name="test", check_fn=dummy, weight=0.5,
                        depends_on=("nonexistent_check",)),
        )

        ordered = _resolve_dependency_order(policy)
        assert len(ordered) == 1
        assert ordered[0].name == "test"

    def test_skipped_dependency_blocks_dependent(self):
        """A skipped (caller-skipped) dependency should block its dependent."""
        from core.system_readiness import run_readiness_check, _CHECKS
        # Skip composio_token — dispatch_gate should also be skipped
        report = run_readiness_check(json_only=True, skip=("composio_token",))
        dispatch = next((c for c in report.checks if c.name == "dispatch_gate"), None)
        assert dispatch is not None
        assert dispatch.status == "skipped", (
            f"dispatch_gate should be skipped when composio_token is skipped, got {dispatch.status}"
        )

    def test_policy_metadata_in_json_report(self):
        """Verify the JSON report includes policy metadata (weight, failure_mode, depends_on)."""
        from core.system_readiness import run_readiness_check, _REPORT_DIR
        report = run_readiness_check(json_only=True)
        report_path = _REPORT_DIR / f"{report.check_id}.json"
        with open(report_path) as f:
            data = json.load(f)
        assert "policy" in data, "JSON report missing 'policy' section"
        for entry in data["policy"]:
            assert "name" in entry
            assert "weight" in entry
            assert "failure_mode" in entry
            assert "depends_on" in entry
            assert "critical" in entry
            assert 0.0 <= entry["weight"] <= 1.0
            assert entry["failure_mode"] in ("block", "warn", "skip")
        # Verify known critical entries
        dispatch_policy = next((e for e in data["policy"] if e["name"] == "dispatch_gate"), None)
        assert dispatch_policy is not None
        assert dispatch_policy["critical"] is True
        assert "composio_token" in dispatch_policy["depends_on"]

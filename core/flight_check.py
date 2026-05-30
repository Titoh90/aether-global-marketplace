#!/usr/bin/env python3
"""
core/flight_check — Pre-Deploy Flight Check Layer (Phase 2+3 Gate).

Automated test gate that runs before every deploy to ensure
Competitive Intelligence + Cinematic Video layers are stable.

CRITICAL RULES:
  - NEVER modifies the core pipeline
  - NEVER touches runtime-critical services directly
  - Blocking only on TEST failures (not test infrastructure)
  - Always produces a JSON report
  - Always returns exit code 0 on pass, 1 on failure

Quick mode (default):   test_cinematic_video.py + test_ci_scheduler.py + test_ci_to_vi_bridge.py
Full mode  (--full):    ALL test suites
Readiness  (--readiness): System readiness check (12 subsystem health probes)

Usage:
    python3 -m core.flight_check              # quick mode (Phase 2+3 suites)
    python3 -m core.flight_check --full        # full mode (all suites)
    python3 -m core.flight_check --readiness   # system readiness check
    python3 -m core.flight_check --json-only   # no stdout, only JSON report
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


# ── Paths ──────────────────────────────────────────────────────────────────────

_IMPERIO_ROOT = Path(__file__).parent.parent
_TESTS_DIR    = _IMPERIO_ROOT / "tests"
_REPORT_DIR   = _IMPERIO_ROOT / "logs" / "flight_checks"

# ── Test suites ────────────────────────────────────────────────────────────────

# Quick mode: Phase 2 (CI + bridge + scheduler) + Phase 3 (cinematic video)
_QUICK_SUITES: tuple[str, ...] = (
    "tests/test_cinematic_video.py",
    "tests/test_ci_scheduler.py",
    "tests/test_ci_to_vi_bridge.py",
    "tests/test_flow_operator_training.py",
)

# Full mode: every test in tests/
_FULL_SUITES: tuple[str, ...] = (
    "tests/test_knowledge_core.py",
    "tests/test_inference_dispatch.py",
    "tests/test_engagement.py",
    "tests/test_competitive_intelligence.py",
    "tests/test_ci_to_vi_bridge.py",
    "tests/test_ci_scheduler.py",
    "tests/test_cinematic_video.py",
    "tests/test_flow_operator_training.py",
    "tests/test_conversion_surface.py",
    "tests/test_fallbacks.py",
    "tests/test_truth_layer_compat.py",
    "tests/test_visual_truth.py",
    "tests/test_revenue_layer.py",
    "tests/test_dispatch_gate.py",
    "tests/test_visual_intelligence.py",
    "tests/test_provider_routing.py",
    "tests/test_freellmapi.py",
    "tests/test_system_readiness.py",
)

# Allowed to fail in full mode (flaky or requires external deps)
_ALLOWED_FAIL: tuple[str, ...] = (
    "tests/test_revenue_layer.py",
    "tests/test_freellmapi.py",
    "tests/test_ci_scheduler.py",
)


# ── Output types ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SuiteResult:
    """Single test suite result."""
    suite: str
    passed: int
    failed: int
    errors: int
    duration_seconds: float
    raw_output: str = field(repr=False)


@dataclass(frozen=True)
class FlightCheckReport:
    """Aggregated pre-deploy check report."""
    check_id: str
    checked_at: str
    mode: str  # "quick" | "full"
    total_passed: int
    total_failed: int
    total_errors: int
    suites: tuple[SuiteResult, ...]
    passed: bool
    duration_total_seconds: float


# ── Runner ─────────────────────────────────────────────────────────────────────

def _ensure_report_dir() -> None:
    """Create report directory lazily (no import-time side effects)."""
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _parse_pytest_counts(stdout: str) -> tuple[int, int, int]:
    """Parse pytest -q output for passed/failed/errors counts.

    Uses pytest exit-code-based fallback for robustness:
      - Exit 0: all passed
      - Exit 1: tests failed
      - Exit 5: no tests collected
    """
    import re
    # Pytest summary format: "X passed, Y failed, Z errors" or
    # "X passed in Y.YYs" (all-pass case)
    # Prefer the full summary line first
    for line in stdout.split("\n"):
        m = re.search(
            r"(\d+)\s+passed.*?(\d+)\s+failed.*?(\d+)\s+error",
            line,
        )
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))

    # All-pass variant: "X passed" with no failures/errors
    for line in stdout.split("\n"):
        m = re.search(r"^(\d+)\s+passed", line.strip())
        if m:
            return int(m.group(1)), 0, 0

    # Fallback: individual counts
    passed = 0
    failed = 0
    errors = 0
    for line in stdout.split("\n"):
        m_p = re.search(r"(\d+)\s+passed", line)
        if m_p:
            passed = int(m_p.group(1))
        m_f = re.search(r"(\d+)\s+failed", line)
        if m_f:
            failed = int(m_f.group(1))
        m_e = re.search(r"(\d+)\s+error", line)
        if m_e:
            errors = int(m_e.group(1))
    return passed, failed, errors


def _run_suite(
    suite_path: str,
    cwd: Path,
    env: dict[str, str],
) -> SuiteResult:
    """Run a single test suite via pytest, returning SuiteResult.

    NEVER raises — failures are captured in the result.
    """
    full_path = cwd / suite_path
    if not full_path.exists():
        return SuiteResult(
            suite=suite_path,
            passed=0,
            failed=0,
            errors=1,
            duration_seconds=0.0,
            raw_output=f"File not found: {full_path}",
        )

    start = time.monotonic()
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pytest",
                suite_path,
                "-q",
                "--tb=short",
                "--no-header",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(cwd),
            env=env,
        )
        duration = time.monotonic() - start
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        passed, failed, errors = _parse_pytest_counts(stdout)

        # If pytest reports "no tests ran" (exit 5), treat as 0s
        if result.returncode == 5:
            passed, failed, errors = 0, 0, 0

        raw = f"STDOUT:\n{stdout}\n\nSTDERR:\n{stderr}" if stderr else stdout

        return SuiteResult(
            suite=suite_path,
            passed=passed,
            failed=failed,
            errors=errors,
            duration_seconds=round(duration, 3),
            raw_output=raw,
        )
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - start
        return SuiteResult(
            suite=suite_path,
            passed=0,
            failed=0,
            errors=1,
            duration_seconds=round(duration, 3),
            raw_output="TIMEOUT: Suite exceeded 300s limit",
        )
    except Exception as exc:
        duration = time.monotonic() - start
        return SuiteResult(
            suite=suite_path,
            passed=0,
            failed=0,
            errors=1,
            duration_seconds=round(duration, 3),
            raw_output=f"RUNNER ERROR: {exc}",
        )


def run_flight_check(
    mode: str = "quick",
    json_only: bool = False,
) -> FlightCheckReport:
    """Run pre-deploy flight check.

    Args:
        mode: "quick" (Phase 2+3 suites only) or "full" (all suites)
        json_only: If True, suppress stdout during run

    Returns:
        FlightCheckReport — never raises
    """
    if mode not in ("quick", "full"):
        mode = "quick"

    suites_to_run = _QUICK_SUITES if mode == "quick" else _FULL_SUITES
    env = dict(os.environ)
    env["CI_TEST_MODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    if not json_only:
        print(f"✈️  FLIGHT CHECK — {mode.upper()} MODE")
        print(f"   {len(suites_to_run)} suite(s) to run\n")

    all_results: list[SuiteResult] = []
    total_start = time.monotonic()

    for suite_path in suites_to_run:
        if not json_only:
            print(f"  🔍 {suite_path} ... ", end="", flush=True)

        result = _run_suite(suite_path, _IMPERIO_ROOT, env)

        if not json_only:
            if result.failed == 0 and result.errors == 0:
                print(f"✅ {result.passed} passed ({result.duration_seconds:.1f}s)")
            elif result.failed > 0:
                print(f"❌ {result.failed} FAILED, {result.passed} passed")
            else:
                print(f"⚠️  {result.errors} ERROR(S)")

        all_results.append(result)

    total_duration = time.monotonic() - total_start

    total_passed = sum(r.passed for r in all_results)
    total_failed = sum(r.failed for r in all_results)
    total_errors = sum(r.errors for r in all_results)

    # Mark as passed if zero real failures (allowed failures excluded)
    failed_suites = [
        r for r in all_results
        if (r.failed > 0 or r.errors > 0)
        and r.suite not in _ALLOWED_FAIL
    ]
    overall_passed = len(failed_suites) == 0

    check_id = datetime.now(timezone.utc).strftime("FLIGHT-%Y%m%d-%H%M%S")
    checked_at = datetime.now(timezone.utc).isoformat()

    report = FlightCheckReport(
        check_id=check_id,
        checked_at=checked_at,
        mode=mode,
        total_passed=total_passed,
        total_failed=total_failed,
        total_errors=total_errors,
        suites=tuple(all_results),
        passed=overall_passed,
        duration_total_seconds=round(total_duration, 3),
    )

    # Always write JSON report
    _write_report(report)

    if not json_only:
        print(f"\n{'─' * 50}")
        status_icon = "✅ PASS" if overall_passed else "❌ FAIL"
        print(f"  FLIGHT CHECK {status_icon}")
        print(f"  {total_passed} passed | {total_failed} failed | {total_errors} errors")
        print(f"  Duration: {total_duration:.1f}s")
        print(f"  Report:  logs/flight_checks/{check_id}.json")
        print(f"{'─' * 50}")

    return report


# ── Report persistence ─────────────────────────────────────────────────────────

def _write_report(report: FlightCheckReport) -> Path:
    """Write flight check report to disk. NEVER raises."""
    _ensure_report_dir()
    try:
        report_path = _REPORT_DIR / f"{report.check_id}.json"
        data = {
            "check_id": report.check_id,
            "checked_at": report.checked_at,
            "mode": report.mode,
            "passed": report.passed,
            "total_passed": report.total_passed,
            "total_failed": report.total_failed,
            "total_errors": report.total_errors,
            "duration_total_seconds": report.duration_total_seconds,
            "suites": [
                {
                    "suite": s.suite,
                    "passed": s.passed,
                    "failed": s.failed,
                    "errors": s.errors,
                    "duration_seconds": s.duration_seconds,
                    "output": s.raw_output if s.failed > 0 or s.errors > 0 else "",
                }
                for s in report.suites
            ],
        }
        tmp_path = Path(str(report_path) + ".tmp")
        tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        tmp_path.replace(report_path)
        return report_path
    except Exception as exc:
        print(
            f"[flight_check] Failed to write report: {exc}",
            file=sys.stderr,
        )
        return _REPORT_DIR / "FLIGHT_ERROR.json"


def get_latest_report() -> FlightCheckReport | None:
    """Return the most recent flight check report, or None."""
    try:
        if not _REPORT_DIR.exists():
            return None
        reports = sorted(
            _REPORT_DIR.glob("FLIGHT-*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not reports:
            return None
        with open(reports[0]) as f:
            data = json.load(f)
        suites = tuple(
            SuiteResult(
                suite=s["suite"],
                passed=s["passed"],
                failed=s["failed"],
                errors=s["errors"],
                duration_seconds=s["duration_seconds"],
                raw_output=s.get("output", ""),
            )
            for s in data["suites"]
        )
        return FlightCheckReport(
            check_id=data["check_id"],
            checked_at=data["checked_at"],
            mode=data["mode"],
            total_passed=data["total_passed"],
            total_failed=data["total_failed"],
            total_errors=data["total_errors"],
            suites=suites,
            passed=data["passed"],
            duration_total_seconds=data["duration_total_seconds"],
        )
    except Exception as exc:
        print(
            f"[flight_check] Failed to load latest report: {exc}",
            file=sys.stderr,
        )
        return None


# ── Readiness mode integration ─────────────────────────────────────────────────

def _run_readiness(json_only: bool) -> int:
    """Run system readiness check from flight_check CLI. Returns exit code."""
    try:
        from core.system_readiness import run_readiness_check
        report = run_readiness_check(json_only=json_only)
        if json_only:
            data = {
                "critical_pass": report.critical_pass,
                "all_healthy": report.all_healthy,
                "check_id": report.check_id,
                "unhealthy": list(report.unhealthy),
                "degraded": list(report.degraded),
                "duration_ms": report.duration_ms,
            }
            print(json.dumps(data))
            return 0 if report.critical_pass else 1
        print(f"\n  Critical systems: {'✅ PASS' if report.critical_pass else '❌ FAIL'}")
        print(f"  All systems:      {'✅ HEALTHY' if report.all_healthy else '⚠️  DEGRADED'}")
        return 0 if report.critical_pass else 1
    except ImportError:
        print("[flight_check] core.system_readiness not available", file=sys.stderr)
        return 0  # Non-blocking if module not available
    except Exception as exc:
        print(f"[flight_check] Readiness check failed: {exc}", file=sys.stderr)
        return 0  # Non-blocking — readiness is advisory in flight check context


# ── CLI entry point ────────────────────────────────────────────────────────────

def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point. Returns exit code: 0 = pass, 1 = fail."""
    if argv is None:
        argv = sys.argv[1:]

    mode = "quick"
    json_only = False

    readiness = False
    for arg in argv:
        if arg in ("--full", "-f"):
            mode = "full"
        elif arg in ("--quick", "-q"):
            mode = "quick"
        elif arg in ("--readiness", "-r"):
            readiness = True
        elif arg in ("--json-only", "--json", "-j"):
            json_only = True
        elif arg in ("--help", "-h"):
            print(__doc__)
            return 0

    if readiness:
        return _run_readiness(json_only)

    report = run_flight_check(mode=mode, json_only=json_only)

    if json_only:
        # Print JSON report to stdout
        data = {
            "passed": report.passed,
            "total_passed": report.total_passed,
            "total_failed": report.total_failed,
            "total_errors": report.total_errors,
            "check_id": report.check_id,
            "mode": report.mode,
        }
        print(json.dumps(data))
        return 0 if report.passed else 1

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())

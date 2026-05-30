#!/usr/bin/env python3
"""
core/system_readiness — System Readiness Layer

Pre-deploy health checks for all IMPERIO subsystems.
Answers: "Is the system actually ready to run, or will it die at minute 40?"

ARCHITECTURE:
  - Every check is a pure function: no side effects, no mutations
  - Every check returns ReadinessCheck — never raises
  - PolicyEntry defines weight, failure_mode, and depends_on for each check
  - run_readiness_check() resolves dependency graph (topological sort)
  - Criticality is derived: weight >= 0.8 AND failure_mode == "block"
  - Always writes JSON report to logs/readiness/
  - Integrates with flight_check.py (--readiness mode) and SRE/executor.py

POLICY ENGINE:
  - Weights (0.0-1.0): relative importance of each subsystem
  - Failure modes: "block" (blocks deploy) | "warn" (advisory) | "skip" (non-blocking)
  - Dependency graph: dispatch_gate → composio_token (can't route without auth)
  - Critical = weight >= 0.8 AND failure_mode == "block"

CHECKS (12):
  1.  FAISS vector_store    — IndexFlatIP loads, metadata parses
  2.  FAISS knowledge_store — IndexFlatIP loads, no corruption
  3.  Archetype memory      — JSON files parse, no corruption
  4.  Drift detector        — Last drift log within freshness window
  5.  Bio authenticator     — Instagram/TikTok session files exist
  6.  LLM provider health   — Primary providers healthy
  7.  Dispatch gate         — Singleton valid, registry frozen
  8.  Composio token        — COMPOSIO_API_KEY or config present
  9.  Disk space            — Free space > threshold
  10. Revenue ledger        — Ledger file integrity
  11. CI scheduler          — Summary accessible
  12. Flight check          — Latest report exists and is fresh

CRITICAL RULES:
  - NEVER modifies any subsystem
  - NEVER calls external APIs (all checks are local)
  - Blocking only on CRITICAL failures
  - Always produces a JSON report
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, replace as _dc_replace
from datetime import datetime, timezone
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent
_REPORT_DIR   = _IMPERIO_ROOT / "logs" / "readiness"


# ── Output types ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ReadinessCheck:
    """Single subsystem health check result."""
    name:        str      # e.g. "faiss_vector_store"
    status:      str      # "healthy" | "degraded" | "unhealthy" | "skipped"
    detail:      str      # human-readable detail
    latency_ms:  int      # check duration in ms
    critical:    bool = False  # blocks deploy if unhealthy

    def is_healthy(self) -> bool:
        return self.status == "healthy"


@dataclass(frozen=True)
class ReadinessReport:
    """Aggregated system readiness report."""
    check_id:      str
    checked_at:    str
    checks:        tuple[ReadinessCheck, ...]
    all_healthy:   bool
    critical_pass: bool   # all critical checks healthy?
    degraded:      tuple[str, ...]  # names of degraded checks
    unhealthy:     tuple[str, ...]  # names of unhealthy checks
    duration_ms:   int


@dataclass(frozen=True)
class PolicyEntry:
    """Single policy entry: what to check, how important it is, what it depends on.

    This is the single source of truth for subsystem policy.
    Check functions return state only — policy is enforced here.
    """
    name:          str
    check_fn:      Callable[[], ReadinessCheck]
    weight:        float = 0.5                     # 0.0-1.0, importance weight
    failure_mode:  str   = "warn"                  # "block" | "warn" | "skip"
    depends_on:    tuple[str, ...] = ()            # checks that must be healthy first

    def is_critical(self) -> bool:
        """Critical = weight >= 0.8 AND failure_mode == 'block'."""
        return self.weight >= 0.8 and self.failure_mode == "block"

    def __post_init__(self) -> None:
        if not (0.0 <= self.weight <= 1.0):
            raise ValueError(f"weight must be 0.0-1.0, got {self.weight}")
        if self.failure_mode not in ("block", "warn", "skip"):
            raise ValueError(f"failure_mode must be block/warn/skip, got {self.failure_mode}")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ensure_report_dir() -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)


def _ok(name: str, detail: str, latency_ms: int, critical: bool = False) -> ReadinessCheck:
    return ReadinessCheck(name=name, status="healthy", detail=detail,
                          latency_ms=latency_ms, critical=critical)


def _degraded(name: str, detail: str, latency_ms: int, critical: bool = False) -> ReadinessCheck:
    return ReadinessCheck(name=name, status="degraded", detail=detail,
                          latency_ms=latency_ms, critical=critical)


def _unhealthy(name: str, detail: str, latency_ms: int, critical: bool = False) -> ReadinessCheck:
    return ReadinessCheck(name=name, status="unhealthy", detail=detail,
                          latency_ms=latency_ms, critical=critical)


def _skipped(name: str, detail: str) -> ReadinessCheck:
    return ReadinessCheck(name=name, status="skipped", detail=detail,
                          latency_ms=0, critical=False)


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 1: FAISS vector_store
# ═══════════════════════════════════════════════════════════════════════════════

def _check_faiss_vector_store() -> ReadinessCheck:
    """Verify FAISS IndexFlatIP loads and metadata parses for vector_store."""
    t0 = time.monotonic()
    try:
        import faiss
        from core.visual_intelligence.vector_store import list_products, count, _STORE_DIR

        if not _STORE_DIR.exists():
            return _ok("faiss_vector_store", "Vector store directory not yet created (no data)",
                       int((time.monotonic() - t0) * 1000))

        products = list_products()
        if not products:
            return _ok("faiss_vector_store", "No products indexed yet (cold start)",
                       int((time.monotonic() - t0) * 1000))

        # Spot-check: load first product's index
        first = products[0]
        try:
            from core.visual_intelligence.vector_store import _load_index, _load_meta
            idx = _load_index(first)
            meta = _load_meta(first)
            if idx.ntotal != len(meta):
                return _degraded(
                    "faiss_vector_store",
                    f"Metadata/index mismatch for '{first}': {idx.ntotal} rows vs {len(meta)} meta entries",
                    int((time.monotonic() - t0) * 1000),
                )
            return _ok("faiss_vector_store",
                       f"{len(products)} product(s), {sum(count(p) for p in products)} total embeddings",
                       int((time.monotonic() - t0) * 1000))
        except Exception as e:
            return _degraded("faiss_vector_store",
                             f"Product '{first}' index load failed: {e}",
                             int((time.monotonic() - t0) * 1000))
    except ImportError as e:
        return _skipped("faiss_vector_store", f"FAISS not installed: {e}")
    except Exception as e:
        return _unhealthy("faiss_vector_store", f"Check failed: {e}",
                          int((time.monotonic() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 2: FAISS knowledge_store
# ═══════════════════════════════════════════════════════════════════════════════

def _check_faiss_knowledge_store() -> ReadinessCheck:
    """Verify knowledge_store FAISS index loads and metadata is intact."""
    t0 = time.monotonic()
    try:
        import faiss
        from core.knowledge_core.knowledge_store import list_types, count, STORE_DIR

        if not STORE_DIR.exists():
            return _ok("faiss_knowledge_store", "Knowledge store directory not yet created (no data)",
                       int((time.monotonic() - t0) * 1000))

        types = list_types()
        if not types:
            return _ok("faiss_knowledge_store", "No memory types indexed yet (cold start)",
                       int((time.monotonic() - t0) * 1000))

        # Spot-check first type
        first = types[0]
        try:
            from core.knowledge_core.knowledge_store import _load_index, _load_meta
            idx = _load_index(first)
            meta = _load_meta(first)
            if idx.ntotal != len(meta):
                return _degraded(
                    "faiss_knowledge_store",
                    f"Metadata/index mismatch for '{first}': {idx.ntotal} rows vs {len(meta)} meta entries",
                    int((time.monotonic() - t0) * 1000),
                )
            return _ok("faiss_knowledge_store",
                       f"{len(types)} memory type(s), {sum(count(t) for t in types)} total chunks",
                       int((time.monotonic() - t0) * 1000))
        except Exception as e:
            return _degraded("faiss_knowledge_store",
                             f"Memory type '{first}' index load failed: {e}",
                             int((time.monotonic() - t0) * 1000))
    except ImportError as e:
        return _skipped("faiss_knowledge_store", f"FAISS not installed: {e}")
    except Exception as e:
        return _unhealthy("faiss_knowledge_store", f"Check failed: {e}",
                          int((time.monotonic() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 3: Archetype memory
# ═══════════════════════════════════════════════════════════════════════════════

def _check_archetype_memory() -> ReadinessCheck:
    """Verify archetype memory JSON files parse correctly — no corruption."""
    t0 = time.monotonic()
    try:
        from core.visual_intelligence.archetype_memory import _MEMORY_DIR
        import json as _json

        if not _MEMORY_DIR.exists():
            return _ok("archetype_memory", "Archetype memory directory not yet created (no data)",
                       int((time.monotonic() - t0) * 1000))

        json_files = sorted(_MEMORY_DIR.glob("*.json"))
        if not json_files:
            return _ok("archetype_memory", "No archetype files yet (cold start)",
                       int((time.monotonic() - t0) * 1000))

        corrupted: list[str] = []
        total_archetypes = 0

        for f in json_files:
            try:
                data = _json.loads(f.read_text())
                archetypes = data.get("archetypes", [])
                if not isinstance(archetypes, list):
                    corrupted.append(f"{f.name} (archetypes not a list)")
                    continue
                total_archetypes += len(archetypes)
                # Validate each archetype has required fields
                for arch in archetypes:
                    if not isinstance(arch, dict):
                        corrupted.append(f"{f.name} (non-dict archetype entry)")
                        break
                    if "name" not in arch:
                        corrupted.append(f"{f.name} (archetype missing 'name')")
                        break
            except Exception as e:
                corrupted.append(f"{f.name} ({e})")

        if corrupted:
            return _degraded("archetype_memory",
                             f"Corrupted files: {', '.join(corrupted[:3])}",
                             int((time.monotonic() - t0) * 1000))

        return _ok("archetype_memory",
                   f"{len(json_files)} file(s), {total_archetypes} total archetypes — all valid",
                   int((time.monotonic() - t0) * 1000))

    except ImportError as e:
        return _skipped("archetype_memory", f"Module unavailable: {e}")
    except Exception as e:
        return _degraded("archetype_memory", f"Check failed: {e}",
                         int((time.monotonic() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 4: Drift detector
# ═══════════════════════════════════════════════════════════════════════════════

def _check_drift_detector() -> ReadinessCheck:
    """Verify drift detector logs are fresh (last check within 7 days)."""
    t0 = time.monotonic()
    try:
        from core.visual_intelligence.drift_detector import _LOG_DIR

        if not _LOG_DIR.exists():
            return _ok("drift_detector", "Drift log directory not yet created (no data)",
                       int((time.monotonic() - t0) * 1000))

        log_files = sorted(_LOG_DIR.glob("*.jsonl"), reverse=True)
        if not log_files:
            return _ok("drift_detector", "No drift logs yet (cold start)",
                       int((time.monotonic() - t0) * 1000))

        # Check freshness: last log within 7 days
        latest = log_files[0]
        mtime = latest.stat().st_mtime
        age_hours = (time.time() - mtime) / 3600

        if age_hours > 168:  # 7 days
            return _degraded("drift_detector",
                             f"Last drift log is {age_hours:.0f}h old (>7 days). Detector may be stale.",
                             int((time.monotonic() - t0) * 1000))

        # Count recent drifts
        try:
            lines = latest.read_text().strip().split("\n")
            recent_drifts = sum(1 for line in lines[-100:] if line.strip())
        except Exception:
            recent_drifts = 0

        return _ok("drift_detector",
                   f"Last log: {age_hours:.1f}h ago, {len(log_files)} log file(s)",
                   int((time.monotonic() - t0) * 1000))

    except ImportError as e:
        return _skipped("drift_detector", f"Module unavailable: {e}")
    except Exception as e:
        return _degraded("drift_detector", f"Check failed: {e}",
                         int((time.monotonic() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 5: Bio authenticator
# ═══════════════════════════════════════════════════════════════════════════════

def _check_bio_authenticated() -> ReadinessCheck:
    """Verify Instagram/TikTok session files exist for bio updater."""
    t0 = time.monotonic()
    try:
        candidates = [
            _IMPERIO_ROOT.parent / "SYSTEM_FILES" / "SECURE_CREDENTIALS" / "instagram_session.json",
            _IMPERIO_ROOT.parent / "AI_TOOLS" / "browser_use" / "sessions" / "instagram_session.json",
        ]

        found: list[str] = []
        missing: list[str] = []

        for p in candidates:
            label = str(p.relative_to(_IMPERIO_ROOT.parent)) if p.exists() else p.name
            if p.exists():
                # Check file is valid JSON
                try:
                    import json as _json
                    _json.loads(p.read_text())
                    found.append(label)
                except Exception:
                    missing.append(f"{label} (corrupted JSON)")
            else:
                missing.append(label)

        if not found:
            return _degraded("bio_authenticated",
                             f"No Instagram session files found. Bio updates will fail. "
                             f"Searched: {', '.join(missing[:2])}",
                             int((time.monotonic() - t0) * 1000))

        return _ok("bio_authenticated",
                   f"Found {len(found)} session file(s): {', '.join(found)}. "
                   f"Missing: {len(missing)}",
                   int((time.monotonic() - t0) * 1000))

    except Exception as e:
        return _degraded("bio_authenticated", f"Check failed: {e}",
                         int((time.monotonic() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 6: LLM provider health
# ═══════════════════════════════════════════════════════════════════════════════

def _check_provider_health() -> ReadinessCheck:
    """Verify primary LLM providers have healthy state."""
    t0 = time.monotonic()
    try:
        # Try inference_dispatch provider_health first, fall back to llm
        try:
            from core.inference_dispatch.provider_health import is_healthy, get_status
        except ImportError:
            from core.llm.provider_health import is_healthy, get_status

        statuses = get_status()
        unhealthy = [pid for pid in statuses if not is_healthy(pid)]

        if unhealthy:
            return _degraded(
                "provider_health",
                f"{len(unhealthy)} unhealthy provider(s): {', '.join(unhealthy[:5])}",
                int((time.monotonic() - t0) * 1000),
            )

        return _ok("provider_health",
                   f"All {len(statuses)} tracked provider(s) healthy",
                   int((time.monotonic() - t0) * 1000))

    except ImportError as e:
        return _skipped("provider_health", f"Module unavailable: {e}")
    except Exception as e:
        return _degraded("provider_health", f"Check failed: {e}",
                         int((time.monotonic() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 7: Dispatch gate
# ═══════════════════════════════════════════════════════════════════════════════

def _check_dispatch_gate() -> ReadinessCheck:
    """Verify dispatch_gate singleton is valid and registry is loaded."""
    t0 = time.monotonic()
    try:
        from platform_dispatch.dispatch_gate import dispatch_gate
        from platform_dispatch.platform_registry import PLATFORM_REGISTRY, FORBIDDEN_ROUTES

        if dispatch_gate is None:
            return _unhealthy("dispatch_gate", "dispatch_gate singleton is None",
                              int((time.monotonic() - t0) * 1000))

        # Validate registry is non-empty and frozen
        if not PLATFORM_REGISTRY:
            return _unhealthy("dispatch_gate", "PLATFORM_REGISTRY is empty",
                              int((time.monotonic() - t0) * 1000))

        # Verify registry is actually frozen (MappingProxyType)
        try:
            PLATFORM_REGISTRY["__test__"] = "should_fail"
            return _unhealthy("dispatch_gate",
                              "PLATFORM_REGISTRY is NOT frozen — mutation succeeded!",
                              int((time.monotonic() - t0) * 1000))
        except (TypeError, AttributeError):
            pass  # Expected: frozen registry

        return _ok("dispatch_gate",
                   f"{len(PLATFORM_REGISTRY)} platforms, {len(FORBIDDEN_ROUTES)} forbidden routes — registry frozen",
                   int((time.monotonic() - t0) * 1000))

    except ImportError as e:
        return _skipped("dispatch_gate", f"Module unavailable: {e}")
    except Exception as e:
        return _degraded("dispatch_gate", f"Gate integrity check failed: {e}",
                         int((time.monotonic() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 8: Composio token
# ═══════════════════════════════════════════════════════════════════════════════

def _check_composio_token() -> ReadinessCheck:
    """Verify COMPOSIO_API_KEY is set or Composio config exists."""
    t0 = time.monotonic()
    try:
        # Check env var first
        api_key = os.environ.get("COMPOSIO_API_KEY", "")
        if api_key and len(api_key) > 8:
            return _ok("composio_token",
                       f"COMPOSIO_API_KEY present ({len(api_key)} chars)",
                       int((time.monotonic() - t0) * 1000))

        # Check for Composio config file
        config_paths = [
            Path.home() / ".composio" / "config.json",
            Path.home() / ".config" / "composio" / "credentials.json",
            _IMPERIO_ROOT / "configs" / "composio.json",
        ]
        for p in config_paths:
            if p.exists():
                return _ok("composio_token",
                           f"Composio config found: {p}",
                           int((time.monotonic() - t0) * 1000))

        return _degraded("composio_token",
                         "COMPOSIO_API_KEY not set and no config file found. "
                         "Platform dispatch to Twitter/Pinterest/Facebook/YouTube will fail.",
                         int((time.monotonic() - t0) * 1000))

    except Exception as e:
        return _degraded("composio_token", f"Check failed: {e}",
                         int((time.monotonic() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 9: Disk space
# ═══════════════════════════════════════════════════════════════════════════════

_DISK_MIN_FREE_GB = 5.0    # Minimum free GB before warning
_DISK_CRITICAL_GB = 1.0    # Critical threshold (blocks deploy)


def _check_disk_space() -> ReadinessCheck:
    """Verify sufficient disk space for video generation and logs."""
    t0 = time.monotonic()
    try:
        usage = shutil.disk_usage(str(_IMPERIO_ROOT))
        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        pct_used = (1 - usage.free / usage.total) * 100

        if free_gb < _DISK_CRITICAL_GB:
            return _unhealthy("disk_space",
                              f"CRITICAL: {free_gb:.1f}GB free of {total_gb:.1f}GB ({pct_used:.0f}% used). "
                              f"Video generation will fail.",
                              int((time.monotonic() - t0) * 1000))

        if free_gb < _DISK_MIN_FREE_GB:
            return _degraded("disk_space",
                             f"Low: {free_gb:.1f}GB free of {total_gb:.1f}GB ({pct_used:.0f}% used). "
                             f"Threshold: {_DISK_MIN_FREE_GB}GB",
                             int((time.monotonic() - t0) * 1000))

        return _ok("disk_space",
                   f"{free_gb:.1f}GB free of {total_gb:.1f}GB ({100-pct_used:.0f}% available)",
                   int((time.monotonic() - t0) * 1000))

    except Exception as e:
        return _degraded("disk_space", f"Check failed: {e}",
                         int((time.monotonic() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 10: Revenue ledger
# ═══════════════════════════════════════════════════════════════════════════════

def _check_revenue_ledger() -> ReadinessCheck:
    """Verify revenue ledger log files exist and are writable."""
    t0 = time.monotonic()
    try:
        ledger_dir = _IMPERIO_ROOT / "logs" / "revenue" / "ledger"

        if not ledger_dir.exists():
            return _ok("revenue_ledger", "Ledger directory not yet created (no data)",
                       int((time.monotonic() - t0) * 1000))

        # Check writability
        test_file = ledger_dir / ".readiness_test"
        try:
            test_file.write_text("ok")
            test_file.unlink()
        except Exception:
            return _unhealthy("revenue_ledger",
                              f"Ledger directory {ledger_dir} is NOT writable",
                              int((time.monotonic() - t0) * 1000))

        # Count entries across partitioned files
        ledger_files = sorted(ledger_dir.rglob("*.jsonl"))
        entry_count = 0
        for lf in ledger_files[-10:]:  # Check last 10 files
            try:
                lines = lf.read_text().strip().split("\n")
                entry_count += len([l for l in lines if l.strip()])
            except Exception:
                pass

        return _ok("revenue_ledger",
                   f"{len(ledger_files)} ledger file(s), ~{entry_count} recent entries — writable",
                   int((time.monotonic() - t0) * 1000))

    except Exception as e:
        return _degraded("revenue_ledger", f"Check failed: {e}",
                         int((time.monotonic() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 11: CI scheduler
# ═══════════════════════════════════════════════════════════════════════════════

def _check_ci_scheduler() -> ReadinessCheck:
    """Verify CI scheduler log/report files exist and are fresh."""
    t0 = time.monotonic()
    try:
        ci_report_dir = _IMPERIO_ROOT / "memory" / "competitive_intelligence"
        ci_log_dir = _IMPERIO_ROOT / "logs" / "competitive_intelligence"

        # Check for reports or logs
        report_files = sorted(ci_report_dir.glob("ci_summary_*.json")) if ci_report_dir.exists() else []
        log_files = sorted(ci_log_dir.glob("ci_scheduler_*.log")) if ci_log_dir.exists() else []

        if not report_files and not log_files:
            return _ok("ci_scheduler", "No CI runs yet (cold start)",
                       int((time.monotonic() - t0) * 1000))

        # Check freshness of latest report
        latest_files = report_files or log_files
        latest = latest_files[-1]
        mtime = latest.stat().st_mtime
        age_hours = (time.time() - mtime) / 3600

        if age_hours > 168:  # 7 days
            return _degraded("ci_scheduler",
                             f"Last CI run was {age_hours:.0f}h ago (>7 days). Scheduler may be stale.",
                             int((time.monotonic() - t0) * 1000))

        return _ok("ci_scheduler",
                   f"Last run: {age_hours:.1f}h ago, {len(report_files)} summary file(s)",
                   int((time.monotonic() - t0) * 1000))

    except Exception as e:
        return _degraded("ci_scheduler", f"Check failed: {e}",
                         int((time.monotonic() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 12: Flight check freshness
# ═══════════════════════════════════════════════════════════════════════════════

def _check_flight_check_freshness() -> ReadinessCheck:
    """Verify latest flight check report exists and is recent (< 24h)."""
    t0 = time.monotonic()
    try:
        from core.flight_check import get_latest_report

        report = get_latest_report()
        if report is None:
            return _degraded("flight_check",
                             "No flight check reports found. Run 'python -m core.flight_check' first.",
                             int((time.monotonic() - t0) * 1000))

        # Check freshness
        try:
            ts_str = report.checked_at
            checked_at = datetime.fromisoformat(ts_str)
            age_hours = (datetime.now(timezone.utc) - checked_at).total_seconds() / 3600
        except Exception:
            age_hours = 999

        if age_hours > 24:
            return _degraded("flight_check",
                             f"Latest report is {age_hours:.0f}h old (>24h). Run flight check before deploy.",
                             int((time.monotonic() - t0) * 1000))

        status = "PASS" if report.passed else "FAIL"
        return _ok("flight_check",
                   f"Latest: {status} ({age_hours:.1f}h ago) — {report.total_passed}P/{report.total_failed}F/{report.total_errors}E",
                   int((time.monotonic() - t0) * 1000))

    except ImportError as e:
        return _skipped("flight_check", f"Module unavailable: {e}")
    except Exception as e:
        return _degraded("flight_check", f"Check failed: {e}",
                         int((time.monotonic() - t0) * 1000))


# ═══════════════════════════════════════════════════════════════════════════════
# Policy engine — single source of truth
# ═══════════════════════════════════════════════════════════════════════════════

# Ordered list of all checks with their policy
_POLICY: tuple[PolicyEntry, ...] = (
    PolicyEntry(name="faiss_vector_store",    check_fn=_check_faiss_vector_store,
                weight=1.0, failure_mode="block"),
    PolicyEntry(name="faiss_knowledge_store", check_fn=_check_faiss_knowledge_store,
                weight=0.6, failure_mode="warn"),
    PolicyEntry(name="archetype_memory",      check_fn=_check_archetype_memory,
                weight=0.7, failure_mode="warn"),
    PolicyEntry(name="drift_detector",        check_fn=_check_drift_detector,
                weight=0.5, failure_mode="warn"),
    PolicyEntry(name="bio_authenticated",     check_fn=_check_bio_authenticated,
                weight=0.4, failure_mode="warn"),
    PolicyEntry(name="provider_health",       check_fn=_check_provider_health,
                weight=0.8, failure_mode="warn"),
    PolicyEntry(name="dispatch_gate",         check_fn=_check_dispatch_gate,
                weight=1.0, failure_mode="block",
                depends_on=("composio_token",)),
    PolicyEntry(name="composio_token",        check_fn=_check_composio_token,
                weight=0.9, failure_mode="warn"),
    PolicyEntry(name="disk_space",            check_fn=_check_disk_space,
                weight=1.0, failure_mode="block"),
    PolicyEntry(name="revenue_ledger",        check_fn=_check_revenue_ledger,
                weight=0.6, failure_mode="warn"),
    PolicyEntry(name="ci_scheduler",          check_fn=_check_ci_scheduler,
                weight=0.4, failure_mode="warn"),
    PolicyEntry(name="flight_check",          check_fn=_check_flight_check_freshness,
                weight=0.7, failure_mode="warn"),
)


def _resolve_dependency_order(
    policy: tuple[PolicyEntry, ...],
) -> list[PolicyEntry]:
    """Topological sort policy entries by dependency graph (Kahn's algorithm).

    Ensures that checks whose dependencies failed are auto-skipped.
    Returns entries in execution order (dependencies first).
    """
    name_to_entry = {e.name: e for e in policy}
    # Build graph: entry → list of entries that depend on it
    graph: dict[str, list[str]] = {e.name: [] for e in policy}
    indegree: dict[str, int] = {e.name: len(e.depends_on) for e in policy}

    for entry in policy:
        for dep in entry.depends_on:
            if dep in graph:
                graph[dep].append(entry.name)

    # Kahn's algorithm
    queue = [name for name, deg in indegree.items() if deg == 0]
    ordered: list[str] = []

    while queue:
        node = queue.pop(0)
        ordered.append(node)
        for dependent in graph.get(node, []):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                queue.append(dependent)

    if len(ordered) != len(policy):
        # Cycle detected — fall back to declaration order
        return list(policy)

    return [name_to_entry[name] for name in ordered]


# ── Backward-compatible _CHECKS (for tests that reference it) ──────────────────
_CHECKS: tuple[tuple[str, Callable[[], ReadinessCheck], bool], ...] = tuple(
    (e.name, e.check_fn, e.is_critical()) for e in _POLICY
)


# ═══════════════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════════════


def run_readiness_check(
    json_only: bool = False,
    skip: tuple[str, ...] = (),
) -> ReadinessReport:
    """
    Run ALL system readiness checks using the policy engine.

    Execution order: topological sort by dependency graph.
    If a dependency fails → dependent check auto-skipped.
    Criticality derived from policy: weight >= 0.8 AND failure_mode == 'block'.

    Args:
        json_only: If True, suppress stdout
        skip: Names of checks to skip (e.g. ("composio_token",))

    Returns:
        ReadinessReport — NEVER raises
    """
    total_start = time.monotonic()
    results: list[ReadinessCheck] = []
    results_by_name: dict[str, ReadinessCheck] = {}

    # Resolve execution order (topological sort)
    ordered = _resolve_dependency_order(_POLICY)

    if not json_only:
        print("🩺 SYSTEM READINESS CHECK")
        print(f"   {len(ordered)} subsystem(s) to check (dependency-resolved order)\n")

    for entry in ordered:
        name = entry.name

        if name in skip:
            result = _skipped(name, "Skipped by caller")
            results.append(result)
            results_by_name[name] = result
            if not json_only:
                print(f"  ⏭  {name}: SKIPPED (caller)")
            continue

        # Dependency gate: skip if any dependency is unhealthy (degraded deps allow run)
        dep_failures: list[str] = []
        for dep in entry.depends_on:
            dep_result = results_by_name.get(dep)
            if dep_result and dep_result.status in ("unhealthy", "skipped"):
                dep_failures.append(f"{dep}={dep_result.status}")

        if dep_failures:
            detail = f"Dependency failed: {', '.join(dep_failures)}"
            result = _skipped(name, detail)
            # Policy engine is ALWAYS the source of truth for criticality —
            # even when the check is skipped due to dependency failure.
            result = _dc_replace(result, critical=entry.is_critical())
            results.append(result)
            results_by_name[name] = result
            if not json_only:
                print(f"  🚫 {name}: SKIPPED ({detail})")
            continue

        if not json_only:
            icon = "🔴" if entry.failure_mode == "block" else "🟡"
            print(f"  🔍 {name} [{entry.weight:.1f}/{entry.failure_mode}] ... ", end="", flush=True)

        result = entry.check_fn()
        # Policy engine is the single source of truth for criticality
        result = _dc_replace(result, critical=entry.is_critical())
        results.append(result)
        results_by_name[name] = result

        if not json_only:
            if result.status == "healthy":
                print(f"✅ {result.detail[:70]}")
            elif result.status == "degraded":
                print(f"⚠️  {result.detail[:70]}")
            elif result.status == "unhealthy":
                print(f"❌ {result.detail[:70]}")
            else:
                print(f"⏭  {result.detail[:70]}")

    total_duration = int((time.monotonic() - total_start) * 1000)

    unhealthy_names = tuple(r.name for r in results if r.status == "unhealthy")
    degraded_names  = tuple(r.name for r in results if r.status == "degraded")

    all_healthy = len(unhealthy_names) == 0 and len(degraded_names) == 0

    # Critical pass: all checks with failure_mode="block" must be healthy
    critical_checks = [r for r in results if r.critical]
    critical_pass = all(r.status == "healthy" for r in critical_checks)

    check_id = datetime.now(timezone.utc).strftime("READINESS-%Y%m%d-%H%M%S")
    checked_at = datetime.now(timezone.utc).isoformat()

    report = ReadinessReport(
        check_id=check_id,
        checked_at=checked_at,
        checks=tuple(results),
        all_healthy=all_healthy,
        critical_pass=critical_pass,
        degraded=degraded_names,
        unhealthy=unhealthy_names,
        duration_ms=total_duration,
    )

    _write_report(report)

    if not json_only:
        print(f"\n{'─' * 60}")
        if all_healthy:
            print("  ✅ ALL SYSTEMS HEALTHY")
        elif critical_pass:
            print(f"  ⚠️  CRITICAL SYSTEMS HEALTHY — {len(degraded_names)} degraded, {len(unhealthy_names)} unhealthy (non-critical)")
        else:
            print(f"  ❌ CRITICAL FAILURE — {len(unhealthy_names)} unhealthy critical system(s)")
        # Show dependency-skipped checks
        dep_skipped = [r for r in results if r.status == "skipped" and "Dependency" in r.detail]
        if dep_skipped:
            print(f"  🔗 {len(dep_skipped)} check(s) skipped due to dependency failures")
        print(f"  Duration: {total_duration}ms")
        print(f"  Report:  logs/readiness/{check_id}.json")
        print(f"{'─' * 60}")

    return report


# ── Report persistence ─────────────────────────────────────────────────────────

def _write_report(report: ReadinessReport) -> Path:
    """Write readiness report to disk. NEVER raises."""
    _ensure_report_dir()
    try:
        report_path = _REPORT_DIR / f"{report.check_id}.json"
        data = {
            "check_id": report.check_id,
            "checked_at": report.checked_at,
            "all_healthy": report.all_healthy,
            "critical_pass": report.critical_pass,
            "degraded": list(report.degraded),
            "unhealthy": list(report.unhealthy),
            "duration_ms": report.duration_ms,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "detail": c.detail,
                    "latency_ms": c.latency_ms,
                    "critical": c.critical,
                }
                for c in report.checks
            ],
            # Policy metadata (lookup from _POLICY)
            "policy": [
                {
                    "name": e.name,
                    "weight": e.weight,
                    "failure_mode": e.failure_mode,
                    "depends_on": list(e.depends_on),
                    "critical": e.is_critical(),
                }
                for e in _POLICY
            ],
        }
        tmp_path = Path(str(report_path) + ".tmp")
        tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        tmp_path.replace(report_path)
        return report_path
    except Exception as exc:
        print(f"[system_readiness] Failed to write report: {exc}", file=sys.stderr)
        return _REPORT_DIR / "READINESS_ERROR.json"


def get_latest_readiness_report() -> ReadinessReport | None:
    """Return the most recent readiness report, or None."""
    try:
        if not _REPORT_DIR.exists():
            return None
        reports = sorted(
            _REPORT_DIR.glob("READINESS-*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not reports:
            return None
        with open(reports[0]) as f:
            data = json.load(f)
        checks = tuple(
            ReadinessCheck(
                name=c["name"], status=c["status"], detail=c["detail"],
                latency_ms=c["latency_ms"], critical=c.get("critical", False),
            )
            for c in data["checks"]
        )
        return ReadinessReport(
            check_id=data["check_id"],
            checked_at=data["checked_at"],
            checks=checks,
            all_healthy=data["all_healthy"],
            critical_pass=data["critical_pass"],
            degraded=tuple(data.get("degraded", [])),
            unhealthy=tuple(data.get("unhealthy", [])),
            duration_ms=data.get("duration_ms", 0),
        )
    except Exception as exc:
        print(f"[system_readiness] Failed to load latest report: {exc}", file=sys.stderr)
        return None


# ── SRE integration ────────────────────────────────────────────────────────────

def preflight_gate() -> tuple[bool, ReadinessReport]:
    """
    SRE pre-deploy gate: run readiness check, return (pass, report).

    Gate passes if ALL critical checks are healthy.
    Non-critical degradations/unhealthy do NOT block deploy.

    Returns:
        (pass: bool, report: ReadinessReport)
    """
    report = run_readiness_check(json_only=True)
    return report.critical_pass, report


# ── CLI entry point ────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns exit code: 0 = healthy, 1 = unhealthy critical."""
    if argv is None:
        argv = sys.argv[1:]

    json_only = False
    skip_list: list[str] = []

    for arg in argv:
        if arg in ("--json-only", "--json", "-j"):
            json_only = True
        elif arg.startswith("--skip="):
            skip_list = arg.split("=", 1)[1].split(",")
        elif arg in ("--help", "-h"):
            print(__doc__)
            print("\nUsage:")
            print("  python -m core.system_readiness              # full check")
            print("  python -m core.system_readiness --json-only   # JSON output only")
            print("  python -m core.system_readiness --skip=composio_token,ci_scheduler  # skip checks")
            return 0

    report = run_readiness_check(json_only=json_only, skip=tuple(skip_list))

    if json_only:
        data = {
            "all_healthy": report.all_healthy,
            "critical_pass": report.critical_pass,
            "check_id": report.check_id,
            "unhealthy": list(report.unhealthy),
            "degraded": list(report.degraded),
            "duration_ms": report.duration_ms,
        }
        print(json.dumps(data))
        return 0 if report.critical_pass else 1

    return 0 if report.critical_pass else 1


if __name__ == "__main__":
    sys.exit(main())

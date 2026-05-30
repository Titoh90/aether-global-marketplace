"""
anomaly_detector.py — Detect anomalies across system state.

Reads circuit breaker state, AI spend, event logs, posting safety,
and system readiness to produce a list of active anomalies.

100% deterministic — no LLM calls.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from core.events.event_types import Severity

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")


@dataclass(frozen=True)
class Anomaly:
    anomaly_id: str
    title: str
    severity: Severity
    category: str
    details: str
    detected_at: str


def detect_anomalies() -> list[Anomaly]:
    """
    Scan system state files for anomalies.
    Returns list of active anomalies, sorted by severity (critical first).
    """
    anomalies = []
    now = time.strftime("%Y-%m-%dT%H:%M:%S")

    # 1. Circuit breaker — any OPEN circuits?
    cb_file = IMPERIO_ROOT / "logs" / "guardrails" / "circuit_breaker_state.json"
    if cb_file.exists():
        try:
            cb_data = json.loads(cb_file.read_text())
            for executor, state in cb_data.items():
                if state.get("state") == "OPEN":
                    anomalies.append(Anomaly(
                        anomaly_id=f"cb_{executor}",
                        title=f"Circuit breaker OPEN: {executor}",
                        severity=Severity.HIGH,
                        category="executor",
                        details=(
                            f"{state.get('consecutive_failures', 0)} consecutive failures. "
                            f"Last error: {state.get('last_failure_error', 'unknown')[:100]}"
                        ),
                        detected_at=now,
                    ))
                elif state.get("state") == "HALF_OPEN":
                    anomalies.append(Anomaly(
                        anomaly_id=f"cb_{executor}_half",
                        title=f"Circuit breaker HALF_OPEN: {executor}",
                        severity=Severity.MEDIUM,
                        category="executor",
                        details="Cooldown elapsed — next call is a test attempt.",
                        detected_at=now,
                    ))
        except (json.JSONDecodeError, KeyError):
            pass

    # 2. AI spend — approaching or over budget?
    spend_file = IMPERIO_ROOT / "logs" / "guardrails" / f"daily_spend_{time.strftime('%Y-%m-%d')}.json"
    if spend_file.exists():
        try:
            spend = json.loads(spend_file.read_text())
            total = spend.get("total_cost_usd", 0)
            import os
            budget = float(os.environ.get("IMPERIO_DAILY_AI_BUDGET_USD", "0") or "0")
            if budget > 0:
                ratio = total / budget
                if ratio >= 1.0:
                    anomalies.append(Anomaly(
                        anomaly_id="budget_exhausted",
                        title="AI budget EXHAUSTED",
                        severity=Severity.HIGH,
                        category="budget",
                        details=f"Spent ${total:.4f} of ${budget:.2f} budget",
                        detected_at=now,
                    ))
                elif ratio >= 0.8:
                    anomalies.append(Anomaly(
                        anomaly_id="budget_warning",
                        title="AI budget 80%+ used",
                        severity=Severity.LOW,
                        category="budget",
                        details=f"Spent ${total:.4f} of ${budget:.2f} ({ratio:.0%})",
                        detected_at=now,
                    ))
        except (json.JSONDecodeError, ValueError):
            pass

    # 3. Posting safety — compute health at runtime
    try:
        import sys as _sys
        _rev = str(IMPERIO_ROOT / "REVENUE")
        if _rev not in _sys.path:
            _sys.path.insert(0, _rev)
        from posting_safety_layer import PostingSafetyLayer
        _safety = PostingSafetyLayer()
        for _plat in ["telegram", "instagram", "twitter", "pinterest", "tiktok"]:
            _health = _safety.compute_account_health(_plat)
            _score = _health.get("score", 100)
            if _score < 60:
                anomalies.append(Anomaly(
                    anomaly_id=f"safety_{_plat}",
                    title=f"Low health score: {_plat}",
                    severity=Severity.MEDIUM,
                    category="executor",
                    details=f"Health: {_score}/100 — {_health.get('status', '?')}",
                    detected_at=now,
                ))
    except Exception:
        pass

    # 4. SSMIE protective mode?
    ssmie_file = IMPERIO_ROOT / "REVENUE" / "ssmie_state.json"
    if ssmie_file.exists():
        try:
            ssmie = json.loads(ssmie_file.read_text())
            if ssmie.get("system_state") == "protective_mode":
                anomalies.append(Anomaly(
                    anomaly_id="ssmie_protective",
                    title="SSMIE in PROTECTIVE mode",
                    severity=Severity.HIGH,
                    category="system",
                    details="Top-level supervisor has activated protective mode. Pipeline may be throttled.",
                    detected_at=now,
                ))
        except (json.JSONDecodeError, KeyError):
            pass

    # 5. Recent event failures (last hour)
    events_file = IMPERIO_ROOT / "logs" / "events" / f"{time.strftime('%Y-%m-%d')}.jsonl"
    if events_file.exists():
        try:
            one_hour_ago = time.time() - 3600
            failure_count = 0
            with open(events_file) as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if "failed" in entry.get("event_type", ""):
                            failure_count += 1
                    except json.JSONDecodeError:
                        continue
            if failure_count >= 5:
                anomalies.append(Anomaly(
                    anomaly_id="failure_spike",
                    title=f"Failure spike: {failure_count} failures today",
                    severity=Severity.MEDIUM,
                    category="system",
                    details=f"{failure_count} failure events in today's log",
                    detected_at=now,
                ))
        except Exception:
            pass

    # Sort: critical > high > medium > low > info
    sev_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2,
                 Severity.LOW: 3, Severity.INFO: 4}
    anomalies.sort(key=lambda a: sev_order.get(a.severity, 5))

    return anomalies

"""
supervisor_loop.py — HERMES cross-system supervisor.

Observes logs, events, and system state. Detects anomalies.
Classifies incidents. Generates reports. Escalates to Telegram.

HERMES NEVER:
- deletes files
- pushes git
- modifies secrets
- executes arbitrary shell commands
- modifies deterministic core (truth_guard, dispatch_gate, revenue_ledger)

HERMES CAN:
- read all logs and state files
- emit events
- generate reports
- request human approval via Telegram
- recommend repairs (but not execute them)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from core.supervisor.anomaly_detector import detect_anomalies, Anomaly
from core.supervisor.incident_classifier import classify_incident, Incident

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
SUPERVISOR_LOG = IMPERIO_ROOT / "logs" / "supervisor.jsonl"


@dataclass
class SupervisorReport:
    """Snapshot of system state from supervisor's perspective."""
    timestamp: str
    anomalies: list[Anomaly]
    incidents: list[Incident]
    pipeline_status: str    # "idle" | "running" | "failed" | "completed"
    executor_health: dict   # {executor: "healthy"|"open"|"half_open"}
    posts_today: int
    failures_today: int
    ai_spend_today: float
    recommendations: list[str]


class HermesSupervisor:
    """
    Cross-system supervisor. Observes, detects, recommends.
    Does NOT execute repairs — only recommends and escalates.
    """

    def __init__(self):
        self._log_file = SUPERVISOR_LOG
        self._log_file.parent.mkdir(parents=True, exist_ok=True)

    def observe(self) -> SupervisorReport:
        """
        Run full observation cycle:
        1. Detect anomalies
        2. Classify any new incidents
        3. Read system state
        4. Generate recommendations
        5. Return report

        Safe to call any time — read-only operations.
        """
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

        # 1. Anomalies
        anomalies = detect_anomalies()

        # 2. Classify incidents from anomalies
        incidents = []
        for anomaly in anomalies:
            incident = classify_incident(
                event_type=anomaly.anomaly_id,
                data={"details": anomaly.details, "category": anomaly.category},
                source="supervisor",
            )
            if incident:
                incidents.append(incident)

        # 3. Read system state
        executor_health = self._get_executor_health()
        posts_today = self._count_posts_today()
        failures_today = self._count_failures_today()
        ai_spend = self._get_ai_spend_today()
        pipeline_status = self._get_pipeline_status()

        # 4. Generate recommendations
        recommendations = self._generate_recommendations(
            anomalies, executor_health, posts_today, failures_today, ai_spend
        )

        report = SupervisorReport(
            timestamp=timestamp,
            anomalies=anomalies,
            incidents=incidents,
            pipeline_status=pipeline_status,
            executor_health=executor_health,
            posts_today=posts_today,
            failures_today=failures_today,
            ai_spend_today=ai_spend,
            recommendations=recommendations,
        )

        # Log observation
        self._log_observation(report)

        return report

    def _get_executor_health(self) -> dict:
        """Read circuit breaker state for all executors."""
        cb_file = IMPERIO_ROOT / "logs" / "guardrails" / "circuit_breaker_state.json"
        if not cb_file.exists():
            return {}
        try:
            data = json.loads(cb_file.read_text())
            return {
                name: state.get("state", "CLOSED").lower()
                for name, state in data.items()
            }
        except Exception:
            return {}

    def _count_posts_today(self) -> int:
        """Count posts from today across all platform logs."""
        today = time.strftime("%Y-%m-%d")
        count = 0
        for log_name in ["instagram_posts.jsonl", "twitter_posts.jsonl",
                         "pinterest_posts.jsonl", "tiktok_posts.jsonl",
                         "posts_log.jsonl"]:
            log_path = IMPERIO_ROOT / "REVENUE" / log_name
            if log_path.exists():
                try:
                    with open(log_path) as f:
                        for line in f:
                            if today in line:
                                count += 1
                except Exception:
                    pass
        return count

    def _count_failures_today(self) -> int:
        """Count failure events from today."""
        events_file = IMPERIO_ROOT / "logs" / "events" / f"{time.strftime('%Y-%m-%d')}.jsonl"
        if not events_file.exists():
            return 0
        count = 0
        try:
            with open(events_file) as f:
                for line in f:
                    if "failed" in line:
                        count += 1
        except Exception:
            pass
        return count

    def _get_ai_spend_today(self) -> float:
        """Get today's AI spend in USD."""
        spend_file = (IMPERIO_ROOT / "logs" / "guardrails"
                      / f"daily_spend_{time.strftime('%Y-%m-%d')}.json")
        if not spend_file.exists():
            return 0.0
        try:
            data = json.loads(spend_file.read_text())
            return data.get("total_cost_usd", 0.0)
        except Exception:
            return 0.0

    def _get_pipeline_status(self) -> str:
        """Check if pipeline is currently running (lock file exists with active PID)."""
        import os
        lock_file = Path("/tmp/imperio-pipeline-master_pipeline.lock")
        if not lock_file.exists():
            return "idle"
        try:
            pid = int(lock_file.read_text().strip())
            # Check if PID is alive
            os.kill(pid, 0)
            return "running"
        except (ValueError, ProcessLookupError, PermissionError):
            return "idle"

    def _generate_recommendations(
        self,
        anomalies: list[Anomaly],
        executor_health: dict,
        posts_today: int,
        failures_today: int,
        ai_spend: float,
    ) -> list[str]:
        """Generate actionable recommendations based on current state."""
        recs = []

        # Open circuits
        open_circuits = [k for k, v in executor_health.items() if v == "open"]
        if open_circuits:
            recs.append(
                f"Executors disabled: {', '.join(open_circuits)}. "
                f"Check platform status and session cookies."
            )

        # High failure rate
        if failures_today > 5:
            recs.append(
                f"{failures_today} failures today — investigate root cause "
                f"via event logs: logs/events/{time.strftime('%Y-%m-%d')}.jsonl"
            )

        # No posts
        if posts_today == 0:
            hour = int(time.strftime("%H"))
            if hour >= 12:
                recs.append("No posts today and it's past noon. Check pipeline execution.")

        # High AI spend
        import os
        budget = float(os.environ.get("IMPERIO_DAILY_AI_BUDGET_USD", "0") or "0")
        if budget > 0 and ai_spend > budget * 0.8:
            recs.append(f"AI spend at ${ai_spend:.4f} — {ai_spend/budget:.0%} of budget.")

        if not recs:
            recs.append("System healthy. No action required.")

        return recs

    def _log_observation(self, report: SupervisorReport) -> None:
        """Append observation to supervisor log."""
        try:
            entry = {
                "ts": report.timestamp,
                "anomalies": len(report.anomalies),
                "incidents": len(report.incidents),
                "pipeline": report.pipeline_status,
                "posts_today": report.posts_today,
                "failures_today": report.failures_today,
                "ai_spend": report.ai_spend_today,
                "recommendations": report.recommendations,
            }
            with open(self._log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def format_report(self, report: SupervisorReport = None) -> str:
        """Format report as human-readable text for Telegram."""
        if report is None:
            report = self.observe()

        lines = []
        lines.append(f"{'='*40}")
        lines.append(f"HERMES STATUS — {report.timestamp}")
        lines.append(f"{'='*40}")
        lines.append(f"Pipeline: {report.pipeline_status.upper()}")
        lines.append(f"Posts today: {report.posts_today}")
        lines.append(f"Failures: {report.failures_today}")
        lines.append(f"AI spend: ${report.ai_spend_today:.4f}")

        if report.executor_health:
            lines.append("\nExecutors:")
            for name, state in report.executor_health.items():
                icon = {"closed": "OK", "open": "DISABLED", "half_open": "TESTING"}.get(state, state)
                lines.append(f"  {name}: {icon}")

        if report.anomalies:
            lines.append(f"\nAnomalies ({len(report.anomalies)}):")
            for a in report.anomalies[:5]:
                lines.append(f"  [{a.severity.value.upper()}] {a.title}")

        if report.recommendations:
            lines.append("\nRecommendations:")
            for r in report.recommendations:
                lines.append(f"  - {r}")

        lines.append(f"{'='*40}")
        return "\n".join(lines)

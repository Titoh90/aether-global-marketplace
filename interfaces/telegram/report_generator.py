"""
report_generator.py — Generate formatted reports for Telegram.

Transforms supervisor data into human-readable Telegram messages.
Supports daily digest, incident summary, and performance reports.
"""

from __future__ import annotations

import time
from pathlib import Path

from core.supervisor.supervisor_loop import HermesSupervisor
from core.events.event_store import EventStore

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")


class ReportGenerator:
    """Generate Telegram-formatted reports from system state."""

    def __init__(self):
        self._supervisor = HermesSupervisor()
        self._event_store = EventStore()

    def daily_digest(self) -> str:
        """
        Full daily digest — meant to be sent once per day.
        Covers: pipeline, posts, failures, AI spend, anomalies, recommendations.
        """
        report = self._supervisor.observe()
        lines = []
        lines.append(f"{'='*35}")
        lines.append("HERMES DAILY DIGEST")
        lines.append(f"{time.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"{'='*35}")

        # Pipeline
        lines.append(f"\nPipeline: {report.pipeline_status.upper()}")
        lines.append(f"Posts hoy: {report.posts_today}")
        lines.append(f"Fallos hoy: {report.failures_today}")
        lines.append(f"AI spend: ${report.ai_spend_today:.4f}")

        # Executor health
        if report.executor_health:
            lines.append("\nExecutors:")
            for name, state in report.executor_health.items():
                icon = {"closed": "OK", "open": "DISABLED", "half_open": "TESTING"}.get(state, state.upper())
                lines.append(f"  {name}: {icon}")

        # Event summary
        counts = self._event_store.count_by_type()
        if counts:
            lines.append("\nEventos por tipo:")
            for et, count in sorted(counts.items(), key=lambda x: -x[1])[:8]:
                lines.append(f"  {et}: {count}")

        # Anomalies
        if report.anomalies:
            lines.append(f"\nAnomalias ({len(report.anomalies)}):")
            for a in report.anomalies[:5]:
                lines.append(f"  [{a.severity.value.upper()}] {a.title}")

        # Recommendations
        if report.recommendations:
            lines.append("\nRecomendaciones:")
            for r in report.recommendations:
                lines.append(f"  - {r}")

        # Revenue snapshot
        revenue = self._get_revenue_snapshot()
        if revenue:
            lines.append("\nRevenue:")
            lines.append(f"  Clicks hoy: {revenue.get('clicks_today', 0)}")
            lines.append(f"  Revenue est.: ${revenue.get('estimated_revenue', 0):.2f}")

        lines.append(f"\n{'='*35}")
        return "\n".join(lines)

    def incident_summary(self, hours: int = 24) -> str:
        """Summary of incidents in the last N hours."""
        report = self._supervisor.observe()
        if not report.incidents:
            return "Sin incidentes en las ultimas 24h."

        lines = [f"Incidentes ({len(report.incidents)}):"]
        for inc in report.incidents:
            lines.append(f"\n[{inc.severity.value.upper()}] {inc.title}")
            lines.append(f"  {inc.details[:150]}")
            lines.append(f"  Accion: {inc.recommended_action[:100]}")
            if inc.requires_approval:
                lines.append(f"  REQUIERE APROBACION: /approve {inc.incident_id}")
        return "\n".join(lines)

    def performance_snapshot(self) -> str:
        """Quick performance metrics."""
        report = self._supervisor.observe()
        lines = [
            "Performance Snapshot:",
            f"  Posts: {report.posts_today}",
            f"  Fallos: {report.failures_today}",
        ]

        # Success rate
        total = report.posts_today + report.failures_today
        if total > 0:
            rate = report.posts_today / total * 100
            lines.append(f"  Success rate: {rate:.0f}%")

        lines.append(f"  AI spend: ${report.ai_spend_today:.4f}")

        return "\n".join(lines)

    def _get_revenue_snapshot(self) -> dict:
        """Read today's revenue data if available."""
        # Check click log
        click_log = IMPERIO_ROOT / "REVENUE" / "click_log.json"
        if not click_log.exists():
            return {}

        today = time.strftime("%Y-%m-%d")
        clicks_today = 0
        try:
            with open(click_log) as f:
                for line in f:
                    if today in line:
                        clicks_today += 1
        except Exception:
            pass

        return {
            "clicks_today": clicks_today,
            "estimated_revenue": 0.0,  # no real revenue tracking yet
        }

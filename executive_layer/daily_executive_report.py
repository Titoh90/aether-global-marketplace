"""
daily_executive_report.py — Generate and send daily executive report.

Runs once per day (triggered by autonomous_loop or cron).
Combines all metrics into a comprehensive executive briefing.
Sends to Telegram and stores in memory.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from executive_layer.system_reader import SystemReader
from executive_layer.llm_reasoning import reason
from executive_layer.memory_adapter import MemoryAdapter

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
REPORTS_DIR = IMPERIO_ROOT / "reports"


class DailyExecutiveReport:
    """Generate comprehensive daily executive briefing."""

    def __init__(self):
        self._reader = SystemReader()
        self._memory = MemoryAdapter()
        # Cache: last Monday we appended the weekly section (prevents double-append
        # if the report regenerates on the same day)
        self._last_weekly_monday: str = ""

    async def generate(self) -> str:
        """Generate full daily executive report with LLM analysis."""
        snap = self._reader.snapshot()
        summary = self._reader.format_executive_summary(snap)

        # ── Weekly creative trends section (Mondays only) ──────────
        weekly_section = ""
        date_slug = time.strftime("%Y-%m-%d")
        if self._is_monday() and date_slug != self._last_weekly_monday:
            self._last_weekly_monday = date_slug
            weekly_section = self._build_weekly_section()

        # LLM-enhanced analysis
        analysis = ""
        try:
            prompt = (
                f"Eres el director ejecutivo de una agencia de marketing de afiliados de Amazon.\n"
                f"Analiza este reporte diario y genera:\n"
                f"1. Assessment general (1 línea)\n"
                f"2. Top 3 prioridades para mañana\n"
                f"3. Riesgos a monitorear\n"
                f"4. Oportunidades detectadas\n\n"
                f"Datos:\n{summary}\n\n"
            )
            if weekly_section:
                prompt += f"Weekly creative trends:\n{weekly_section}\n\n"
            prompt += "Responde en español, conciso, accionable."
            analysis = await reason(prompt, max_tokens=400, temperature=0.3)
        except Exception:
            analysis = "Análisis LLM no disponible."

        # Compose full report
        report = f"{summary}"
        if weekly_section:
            report += f"\n\n── WEEKLY CREATIVE TRENDS ──\n{weekly_section}"
        report += f"\n\n── ANÁLISIS EJECUTIVO ──\n{analysis}"

        # Store in memory
        self._memory.store_report(
            slug=f"daily_{date_slug}",
            content=report,
            tags=["daily", "executive", date_slug],
        )

        # Store raw data
        self._save_report_json(snap, date_slug)

        return report

    def _is_monday(self) -> bool:
        """Check if today is Monday (0 = Monday, 6 = Sunday)."""
        return time.localtime().tm_wday == 0

    def _build_weekly_section(self) -> str:
        """
        Build a weekly creative trends section from the last 7 days
        of meta_cognitive_log.json. Uses shared HermesMetaOrchestrator
        logic for trend computation.

        Returns empty string if no data available.
        """
        import json
        from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

        log_file = IMPERIO_ROOT / "REVENUE" / "meta_cognitive_log.json"
        if not log_file.exists():
            return ""

        try:
            data = json.loads(log_file.read_text())
            if not isinstance(data, list) or not data:
                return ""

            # Filter to last 7 days
            cutoff = time.time() - 604800
            week_cycles = []
            for d in data:
                if not isinstance(d, dict):
                    continue
                ts_str = d.get("timestamp", d.get("generated_at", ""))
                try:
                    ts = time.mktime(time.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S"))
                except Exception:
                    continue
                if ts >= cutoff:
                    week_cycles.append(d)

            if not week_cycles:
                return ""

            return HermesMetaOrchestrator.build_weekly_summary(week_cycles)
        except Exception:
            return ""

    def _save_report_json(self, snap, date_slug: str):
        """Save structured report data as JSON."""
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report_file = REPORTS_DIR / f"executive_{date_slug}.json"
        data = {
            "timestamp": snap.timestamp,
            "pipeline_status": snap.pipeline_status,
            "total_posts": snap.total_posts_today,
            "posts_by_platform": snap.posts_today,
            "failures": snap.failures_today,
            "ai_spend_usd": snap.ai_spend_usd,
            "clicks": snap.clicks_today,
            "campaigns_active": snap.campaigns_active,
            "executor_states": snap.executor_states,
            "platform_health": snap.platform_health,
            "ssmie_mode": snap.ssmie_mode,
        }
        try:
            report_file.write_text(json.dumps(data, indent=2))
        except Exception:
            pass

"""
command_router.py — Route Telegram commands to HERMES subsystems.

All commands are read-only or require explicit approval.
HERMES never executes repairs autonomously.

Commands:
  /status      — Full system status report
  /health      — Executor health (circuit breakers)
  /pipeline    — Pipeline status (running/idle/failed)
  /posts       — Posts count today
  /failures    — Recent failures
  /spend       — AI spend today
  /anomalies   — Active anomalies
  /why_failed  — Last failure details
  /report      — Full formatted report
  /pause       — Pause pipeline (requires confirmation)
  /resume      — Resume pipeline
  /approve     — Approve pending incident action
  /reject      — Reject pending incident action
  /help        — List commands
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from core.supervisor.supervisor_loop import HermesSupervisor
from core.events.event_store import EventStore
from core.creative_intelligence.proactive_digest import (
    build_brand_report,
    build_proactive_digest,
    build_why_creative,
)
from executive_layer.system_reader import SystemReader
from executive_layer.planning_engine import PlanningEngine

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
sys.path.insert(0, str(IMPERIO_ROOT))  # ensure hermes_core is importable

# Pending approval requests: {incident_id: {title, action, timestamp}}
_pending_approvals: dict[str, dict] = {}


class CommandRouter:
    """Route Telegram slash commands to appropriate handlers."""

    def __init__(self):
        self._supervisor = HermesSupervisor()
        self._event_store = EventStore()
        self._system_reader = SystemReader()
        self._planner = PlanningEngine()

    async def handle(self, command: str, args: str, chat_id: int) -> str:
        """
        Route command to handler. Returns response text.

        All handlers are read-only except /pause, /resume, /approve, /reject.
        """
        handlers = {
            "/status": self._cmd_status,
            "/health": self._cmd_health,
            "/pipeline": self._cmd_pipeline,
            "/posts": self._cmd_posts,
            "/failures": self._cmd_failures,
            "/spend": self._cmd_spend,
            "/anomalies": self._cmd_anomalies,
            "/why_failed": self._cmd_why_failed,
            "/report": self._cmd_report,
            "/pause": self._cmd_pause,
            "/resume": self._cmd_resume,
            "/approve": self._cmd_approve,
            "/reject": self._cmd_reject,
            "/executive": self._cmd_executive,
            "/plan": self._cmd_plan,
            "/campaigns": self._cmd_campaigns,
            "/clicks": self._cmd_clicks,
            "/creative": self._cmd_creative,
            "/ideas": self._cmd_creative,
            "/proactive": self._cmd_creative,
            "/digest": self._cmd_digest,
            "/meta": self._cmd_meta,
            "/weekly": self._cmd_weekly,
            "/analyze": self._cmd_analyze,
            "/why_creative": self._cmd_why_creative,
            "/brand_report": self._cmd_brand_report,
            "/help": self._cmd_help,
        }

        handler = handlers.get(command)
        if not handler:
            return f"Comando desconocido: {command}\n/help para ver comandos"

        return await handler(args)

    async def _cmd_status(self, args: str) -> str:
        """Quick system status."""
        report = self._supervisor.observe()
        lines = [
            f"Pipeline: {report.pipeline_status.upper()}",
            f"Posts hoy: {report.posts_today}",
            f"Fallos: {report.failures_today}",
            f"AI spend: ${report.ai_spend_today:.4f}",
            f"Anomalias: {len(report.anomalies)}",
        ]

        # Open circuits
        open_cb = [k for k, v in report.executor_health.items() if v == "open"]
        if open_cb:
            lines.append(f"Executors OPEN: {', '.join(open_cb)}")

        return "\n".join(lines)

    async def _cmd_health(self, args: str) -> str:
        """Executor health details."""
        report = self._supervisor.observe()
        if not report.executor_health:
            return "Sin datos de circuit breaker."

        lines = ["Executor Health:"]
        for name, state in report.executor_health.items():
            icon = {"closed": "OK", "open": "DISABLED", "half_open": "TESTING"}.get(state, state)
            lines.append(f"  {name}: {icon}")
        return "\n".join(lines)

    async def _cmd_pipeline(self, args: str) -> str:
        """Pipeline status."""
        report = self._supervisor.observe()
        status = report.pipeline_status.upper()

        if status == "RUNNING":
            lock_file = Path("/tmp/imperio-pipeline-master_pipeline.lock")
            try:
                pid = lock_file.read_text().strip()
                return f"Pipeline: RUNNING (PID {pid})"
            except Exception:
                return f"Pipeline: RUNNING"
        return f"Pipeline: {status}"

    async def _cmd_posts(self, args: str) -> str:
        """Posts count today."""
        report = self._supervisor.observe()
        return f"Posts hoy: {report.posts_today}"

    async def _cmd_failures(self, args: str) -> str:
        """Recent failures."""
        failures = self._event_store.recent_failures(limit=5)
        if not failures:
            return "Sin fallos recientes."

        lines = [f"Ultimos {len(failures)} fallos:"]
        for f in failures:
            ts = f.get("timestamp", "?")
            et = f.get("event_type", "unknown")
            sev = f.get("severity", "?")
            lines.append(f"  [{sev.upper()}] {et} @ {ts}")
            if f.get("data", {}).get("error"):
                lines.append(f"    Error: {f['data']['error'][:100]}")
        return "\n".join(lines)

    async def _cmd_spend(self, args: str) -> str:
        """AI spend today."""
        report = self._supervisor.observe()
        import os
        budget = float(os.environ.get("IMPERIO_DAILY_AI_BUDGET_USD", "0") or "0")
        msg = f"AI spend hoy: ${report.ai_spend_today:.4f}"
        if budget > 0:
            pct = report.ai_spend_today / budget * 100
            msg += f" ({pct:.0f}% de ${budget:.2f})"
        return msg

    async def _cmd_anomalies(self, args: str) -> str:
        """Active anomalies."""
        report = self._supervisor.observe()
        if not report.anomalies:
            return "Sin anomalias activas."

        lines = [f"Anomalias activas ({len(report.anomalies)}):"]
        for a in report.anomalies:
            lines.append(f"  [{a.severity.value.upper()}] {a.title}")
            lines.append(f"    {a.details[:100]}")
        return "\n".join(lines)

    async def _cmd_why_failed(self, args: str) -> str:
        """Last failure with full details."""
        failures = self._event_store.recent_failures(limit=1)
        if not failures:
            return "Sin fallos recientes."

        f = failures[0]
        lines = [
            f"Ultimo fallo:",
            f"  Tipo: {f.get('event_type', '?')}",
            f"  Severidad: {f.get('severity', '?')}",
            f"  Timestamp: {f.get('timestamp', '?')}",
            f"  Trace ID: {f.get('trace_id', 'none')}",
        ]
        data = f.get("data", {})
        if data.get("error"):
            lines.append(f"  Error: {data['error'][:300]}")
        if data.get("executor"):
            lines.append(f"  Executor: {data['executor']}")
        if data.get("platform"):
            lines.append(f"  Platform: {data['platform']}")
        return "\n".join(lines)

    async def _cmd_report(self, args: str) -> str:
        """Full formatted report."""
        return self._supervisor.format_report()

    async def _cmd_pause(self, args: str) -> str:
        """Pause pipeline — creates pause flag file."""
        pause_file = IMPERIO_ROOT / "logs" / "guardrails" / "pipeline_paused"
        pause_file.parent.mkdir(parents=True, exist_ok=True)
        pause_file.write_text(json.dumps({
            "paused_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "reason": args or "manual pause via Telegram",
        }))
        return "Pipeline PAUSADO. /resume para reanudar."

    async def _cmd_resume(self, args: str) -> str:
        """Resume pipeline — removes pause flag."""
        pause_file = IMPERIO_ROOT / "logs" / "guardrails" / "pipeline_paused"
        if pause_file.exists():
            pause_file.unlink()
            return "Pipeline REANUDADO."
        return "Pipeline no estaba pausado."

    async def _cmd_approve(self, args: str) -> str:
        """Approve a pending incident action."""
        incident_id = args.strip()
        if not incident_id:
            if not _pending_approvals:
                return "Sin aprobaciones pendientes."
            lines = ["Aprobaciones pendientes:"]
            for iid, info in _pending_approvals.items():
                lines.append(f"  {iid}: {info['title']}")
            return "\n".join(lines)

        if incident_id not in _pending_approvals:
            return f"Incidente {incident_id} no encontrado en pendientes."

        info = _pending_approvals.pop(incident_id)
        # Log approval
        log_entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "incident_id": incident_id,
            "action": "approved",
            "title": info["title"],
        }
        log_file = IMPERIO_ROOT / "logs" / "approvals.jsonl"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        return f"APROBADO: {info['title']}\nAccion: {info.get('action', 'N/A')}"

    async def _cmd_reject(self, args: str) -> str:
        """Reject a pending incident action."""
        incident_id = args.strip()
        if not incident_id:
            return "Uso: /reject <incident_id>"

        if incident_id not in _pending_approvals:
            return f"Incidente {incident_id} no encontrado en pendientes."

        info = _pending_approvals.pop(incident_id)
        log_entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "incident_id": incident_id,
            "action": "rejected",
            "title": info["title"],
        }
        log_file = IMPERIO_ROOT / "logs" / "approvals.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        return f"RECHAZADO: {info['title']}"

    async def _cmd_executive(self, args: str) -> str:
        """Full executive summary with all metrics."""
        snap = self._system_reader.snapshot()
        return self._system_reader.format_executive_summary(snap)

    async def _cmd_plan(self, args: str) -> str:
        """Tactical plan for next actions."""
        return self._planner.format_plan()

    async def _cmd_campaigns(self, args: str) -> str:
        """Active campaigns summary."""
        snap = self._system_reader.snapshot()
        if not snap.top_campaigns:
            return "Sin campañas activas."
        lines = [f"Campañas activas ({snap.campaigns_active}):"]
        for c in snap.top_campaigns:
            lines.append(f"\n  {c['name']}")
            lines.append(f"    ASIN: {c['asin']} | Phase: {c['phase']} | Posts: {c['posts']}")
        return "\n".join(lines)

    async def _cmd_clicks(self, args: str) -> str:
        """Click tracking stats."""
        snap = self._system_reader.snapshot()
        return f"Clicks hoy: {snap.clicks_today}\nCampañas activas: {snap.campaigns_active}"

    async def _cmd_creative(self, args: str) -> str:
        """Read-only proactive creative digest."""
        return build_proactive_digest(root=IMPERIO_ROOT, topic=args or "creative")

    async def _cmd_why_creative(self, args: str) -> str:
        """Explain creative repetition/diversity for a campaign."""
        return build_why_creative(product_id=args.strip(), root=IMPERIO_ROOT)

    async def _cmd_brand_report(self, args: str) -> str:
        """Read-only brand consistency report."""
        return build_brand_report(root=IMPERIO_ROOT)

    async def _route_meta_cognitive(self, action: str = "", *, is_weekly: bool = False) -> str:
        """Shared route for /digest, /meta, and /weekly — all three go through hermes_core."""
        import hermes_core
        if is_weekly:
            result = hermes_core.handle_weekly_digest()
        else:
            result = hermes_core.handle_meta_cognitive("", action)
        if result.get("status") == "success":
            return result.get("formatted", "No output")
        return f"Error: {result.get('error', 'unknown')}"

    async def _cmd_digest(self, args: str) -> str:
        """Daily Creative Digest via HermesMetaOrchestrator."""
        return await self._route_meta_cognitive("digest")

    async def _cmd_meta(self, args: str) -> str:
        """Full meta-cognitive system state via HermesMetaOrchestrator."""
        return await self._route_meta_cognitive("meta")

    async def _cmd_weekly(self, args: str) -> str:
        """Weekly creative summary via HermesMetaOrchestrator."""
        return await self._route_meta_cognitive(is_weekly=True)

    async def _cmd_analyze(self, args: str) -> str:
        """LLM-enriched narrative analysis via HermesMetaOrchestrator.

        Calls orchestrator.enrich_with_llm() directly with await — we are
        already in an async context so asyncio.run() is not needed (and would
        crash with 'cannot be called from a running event loop').
        """
        import os

        if os.environ.get("FEATURE_LLM_ANALYSIS", "0") != "1":
            return (
                "🧠 LLM analysis está desactivado.\n"
                "Para activarlo: export FEATURE_LLM_ANALYSIS=1\n"
                "Usa /digest o /meta para el análisis determinista."
            )

        try:
            from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

            orchestrator = HermesMetaOrchestrator()
            output = orchestrator.run_cycle(persist=True)
            formatted = await orchestrator.enrich_with_llm(output)
            return formatted

        except ImportError as e:
            return f"Error: Meta-cognitive module unavailable: {e}"
        except Exception as e:
            return f"Error: {e}"

    async def _cmd_help(self, args: str) -> str:
        """List available commands."""
        return (
            "HERMES Commands:\n"
            "/status — Estado rapido\n"
            "/executive — Resumen ejecutivo completo\n"
            "/health — Salud de executors\n"
            "/pipeline — Estado del pipeline\n"
            "/plan — Plan tactico\n"
            "/posts — Posts de hoy\n"
            "/campaigns — Campañas activas\n"
            "/clicks — Click tracking\n"
            "/creative — Creative Brain digest\n"
            "/ideas — Ideas proactivas\n"
            "/proactive — Digest proactivo\n"
            "/digest — Daily Creative Digest\n"
            "/meta — Meta-cognitive system state\n"
            "/weekly — Weekly creative summary (7-day trends)\n"
            "/analyze — LLM-enriched narrative analysis (FEATURE_LLM_ANALYSIS=1)\n"
            "/why_creative [asin] — Diagnostico creativo\n"
            "/brand_report — Reporte de identidad de marca\n"
            "/failures — Fallos recientes\n"
            "/spend — Gasto AI hoy\n"
            "/anomalies — Anomalias activas\n"
            "/why_failed — Detalle ultimo fallo\n"
            "/report — Reporte supervisor\n"
            "/pause [razon] — Pausar pipeline\n"
            "/resume — Reanudar pipeline\n"
            "/approve [id] — Aprobar accion\n"
            "/reject <id> — Rechazar accion\n"
            "/help — Este mensaje\n\n"
            "O pregunta libremente:\n"
            "'que fallo hoy?'\n"
            "'cuanto gastamos en AI?'\n"
            "'que posteamos manana?'"
        )


def register_approval(incident_id: str, title: str, action: str):
    """Register a pending approval request from supervisor."""
    _pending_approvals[incident_id] = {
        "title": title,
        "action": action,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

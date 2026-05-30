"""
executive_agent.py — HERMES Executive Conversational Intelligence.

The brain of HERMES. Receives free-form questions from operator,
reads system state, and generates intelligent answers.

Uses LLM for conversational responses. Falls back to deterministic
summaries if LLM unavailable.

Safety: READ-ONLY. Never executes actions. Only reads, reasons, responds.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from core.supervisor.supervisor_loop import HermesSupervisor
from core.events.event_store import EventStore
from executive_layer.operator_memory import OperatorMemory
from executive_layer.planning_engine import PlanningEngine
from executive_layer.llm_reasoning import reason

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")


class ExecutiveAgent:
    """
    Conversational executive AI. Answers operator questions
    using live system data.

    Deterministic first — LLM only for natural language formatting.
    """

    def __init__(self):
        self._supervisor = HermesSupervisor()
        self._event_store = EventStore()
        self._memory = OperatorMemory()
        self._planner = PlanningEngine()

    async def answer(self, question: str) -> str:
        """
        Answer an operator question using system data.

        Flow:
        1. Classify question intent
        2. Gather relevant data
        3. Format response (deterministic or LLM)
        """
        # Record question
        self._memory.record_question(question)

        # Classify intent
        intent = self._classify_intent(question)

        # Gather data and respond
        response = await self._handle_intent(intent, question)

        # Record answer
        self._memory.record_answer(response[:500])

        return response

    def _classify_intent(self, question: str) -> str:
        """Classify question into intent category. Deterministic keyword matching."""
        q = question.lower()

        # Failure/error queries
        if any(w in q for w in ["falló", "failed", "fallo", "error", "broke", "roto"]):
            return "failures"

        # Revenue/money queries
        if any(w in q for w in ["revenue", "ingreso", "dinero", "money", "click", "ventas"]):
            return "revenue"

        # Performance/stats
        if any(w in q for w in ["performance", "rendimiento", "outperform", "mejor", "trending"]):
            return "performance"

        # Planning/next actions
        if any(w in q for w in ["mañana", "tomorrow", "post", "postear", "siguiente", "next"]):
            return "planning"

        # Risk/health
        if any(w in q for w in ["riesgo", "risk", "health", "salud", "plataforma", "platform"]):
            return "risk"

        # Spend/budget
        if any(w in q for w in ["spend", "gasto", "budget", "presupuesto", "ai spend", "costo"]):
            return "spend"

        # Campaign queries
        if any(w in q for w in ["campaign", "campaña", "categoria", "category"]):
            return "campaigns"

        # Comments/engagement
        if any(w in q for w in ["comment", "comentario", "engagement", "responder", "unanswered"]):
            return "engagement"

        # Creative intelligence (after campaigns to avoid over-matching on "style"/"estilo")
        if any(w in q for w in ["creative", "creativo", "fatiga", "diversidad", "diversity", "rotación", "rotation"]):
            return "creative"

        # General status
        if any(w in q for w in ["status", "estado", "cómo está", "how", "resumen", "summary"]):
            return "status"

        return "general"

    async def _handle_intent(self, intent: str, question: str) -> str:
        """Route to appropriate handler based on intent."""
        handlers = {
            "failures": self._answer_failures,
            "revenue": self._answer_revenue,
            "performance": self._answer_performance,
            "planning": self._answer_planning,
            "risk": self._answer_risk,
            "spend": self._answer_spend,
            "campaigns": self._answer_campaigns,
            "creative": self._answer_creative,
            "engagement": self._answer_engagement,
            "status": self._answer_status,
            "general": self._answer_general,
        }
        handler = handlers.get(intent, self._answer_general)
        return await handler(question)

    async def _answer_failures(self, q: str) -> str:
        failures = self._event_store.recent_failures(limit=5)
        if not failures:
            return "Sin fallos recientes. Sistema funcionando normal."

        lines = [f"Últimos {len(failures)} fallos:"]
        for f in failures:
            et = f.get("event_type", "unknown")
            ts = f.get("timestamp", "?")
            error = f.get("data", {}).get("error", "sin detalles")[:150]
            lines.append(f"\n• {et} ({ts})")
            lines.append(f"  {error}")

        report = self._supervisor.observe()
        if report.recommendations:
            lines.append("\nRecomendación:")
            lines.append(f"  {report.recommendations[0]}")

        return "\n".join(lines)

    async def _answer_revenue(self, q: str) -> str:
        # Read click data
        click_log = IMPERIO_ROOT / "REVENUE" / "click_log.json"
        today = time.strftime("%Y-%m-%d")
        clicks_today = 0

        if click_log.exists():
            try:
                with open(click_log) as f:
                    for line in f:
                        if today in line:
                            clicks_today += 1
            except Exception:
                pass

        # Read revenue ledger if exists
        ledger_file = IMPERIO_ROOT / "revenue_layer" / "revenue_ledger.jsonl"
        revenue_entries = 0
        if ledger_file.exists():
            try:
                with open(ledger_file) as f:
                    for line in f:
                        if today in line:
                            revenue_entries += 1
            except Exception:
                pass

        report = self._supervisor.observe()
        return (
            f"Revenue snapshot:\n"
            f"  Clicks hoy: {clicks_today}\n"
            f"  Posts hoy: {report.posts_today}\n"
            f"  Entradas ledger hoy: {revenue_entries}\n"
            f"  (Revenue real requiere Amazon Associates data — API pendiente)"
        )

    async def _answer_performance(self, q: str) -> str:
        report = self._supervisor.observe()
        total = report.posts_today + report.failures_today
        success_rate = (report.posts_today / total * 100) if total > 0 else 0

        lines = [
            "Performance hoy:",
            f"  Posts exitosos: {report.posts_today}",
            f"  Fallos: {report.failures_today}",
            f"  Success rate: {success_rate:.0f}%",
            f"  AI spend: ${report.ai_spend_today:.4f}",
        ]

        # Platform breakdown
        if report.executor_health:
            lines.append("\nSalud por plataforma:")
            for name, state in report.executor_health.items():
                icon = {"closed": "✅", "open": "❌", "half_open": "⚠️"}.get(state, "?")
                lines.append(f"  {icon} {name}")

        return "\n".join(lines)

    async def _answer_planning(self, q: str) -> str:
        plan = self._planner.generate_plan()
        return self._planner.format_plan(plan)

    async def _answer_risk(self, q: str) -> str:
        report = self._supervisor.observe()
        if not report.anomalies:
            return "Sin riesgos activos. Sistema saludable."

        lines = ["Riesgos activos:"]
        for a in report.anomalies:
            lines.append(f"\n[{a.severity.value.upper()}] {a.title}")
            lines.append(f"  {a.details[:150]}")

        if report.recommendations:
            lines.append("\nAcciones recomendadas:")
            for r in report.recommendations:
                lines.append(f"  → {r}")

        return "\n".join(lines)

    async def _answer_spend(self, q: str) -> str:
        report = self._supervisor.observe()
        import os
        budget = float(os.environ.get("IMPERIO_DAILY_AI_BUDGET_USD", "0") or "0")

        lines = [f"AI Spend hoy: ${report.ai_spend_today:.4f}"]
        if budget > 0:
            pct = report.ai_spend_today / budget * 100
            lines.append(f"Budget: ${budget:.2f} ({pct:.0f}% usado)")
            if pct > 80:
                lines.append("⚠ Acercándose al límite — considerar reducir generaciones")
        else:
            lines.append("Sin budget configurado (IMPERIO_DAILY_AI_BUDGET_USD)")

        return "\n".join(lines)

    async def _answer_campaigns(self, q: str) -> str:
        # Read campaigns (nested under "campaigns" key)
        cm_file = IMPERIO_ROOT / "REVENUE" / "campaigns.json"
        if not cm_file.exists():
            return "Sin datos de campaña disponibles."

        try:
            raw = json.loads(cm_file.read_text())
            campaigns = raw.get("campaigns", raw)
            lines = ["Campañas activas:"]
            for asin, data in list(campaigns.items())[:10]:
                name = data.get("product_name", asin)[:40]
                phase = data.get("phase", "?")
                posts = data.get("posts_count", data.get("total_posts", 0))
                lines.append(f"\n  {name}")
                lines.append(f"    ASIN: {asin} | Phase: {phase} | Posts: {posts}")
            return "\n".join(lines)
        except Exception:
            return "Error leyendo campaigns.json"

    async def _answer_creative(self, q: str) -> str:
        """
        Answer creative intelligence questions.
        Uses ProactiveBrain for style rotation, fatigue detection, and ideas.
        Read-only advisory — never mutates production pipeline.
        """
        try:
            from core.creative_intelligence.proactive_brain import ProactiveBrain
            brain = ProactiveBrain()

            # Check for specific product query
            snapshot = brain.get_snapshot(force_refresh=True)
            campaigns = snapshot.product_signals

            # Determine what the user is asking about
            q_lower = q.lower()

            # Style/fatigue questions
            if any(w in q_lower for w in ["fatiga", "fatigue", "repetido", "repetition"]):
                if campaigns:
                    fatigued = sorted(campaigns, key=lambda ps: -ps.style_fatigue_score)
                    lines = ["🎨 Style Fatigue Report:"]
                    for ps in fatigued[:5]:
                        icon = "🔴" if ps.style_fatigue_score > 0.5 else "🟡" if ps.style_fatigue_score > 0.2 else "🟢"
                        lines.append(
                            f"  {icon} {ps.product_name}: {ps.current_style} "
                            f"(fatigue: {ps.style_fatigue_score:.2f}, {ps.repetition_count}x)"
                        )
                    return "\n".join(lines)
                return "No fatigue data available — run creative cycle first."

            # Rotation recommendations
            if any(w in q_lower for w in ["rotación", "rotation", "cambiar", "switch", "alternativa"]):
                if campaigns:
                    lines = ["🔄 Style Rotation Recommendations:"]
                    for ps in campaigns[:3]:
                        rr = brain.get_style_rotation(ps.product_id)
                        lines.append(
                            f"  {ps.product_name}: {rr.current_style} → "
                            f"{rr.recommended_style} ({rr.fatigue_level})"
                        )
                        lines.append(f"    {rr.reason}")
                    return "\n".join(lines)
                return "No campaign data for rotation analysis."

            # General creative status
            return brain.format_proactive_digest()

        except Exception as e:
            return f"Creative intelligence module unavailable: {e}"

    async def _answer_engagement(self, q: str) -> str:
        # Check engagement logs
        eng_log = IMPERIO_ROOT / "engagement_engine" / "response_log.jsonl"
        today = time.strftime("%Y-%m-%d")
        today_responses = 0

        if eng_log.exists():
            try:
                with open(eng_log) as f:
                    for line in f:
                        if today in line:
                            today_responses += 1
            except Exception:
                pass

        return (
            f"Engagement hoy:\n"
            f"  Respuestas generadas: {today_responses}\n"
            f"  (Engagement engine en shadow mode — monitoreo activo)"
        )

    async def _answer_status(self, q: str) -> str:
        return self._supervisor.format_report()

    async def _answer_general(self, q: str) -> str:
        """Fallback — use LLM to answer free-form questions with system context."""
        report = self._supervisor.observe()
        context = self._memory.format_for_prompt(limit=5)

        system_data = (
            f"Pipeline: {report.pipeline_status}\n"
            f"Posts hoy: {report.posts_today}\n"
            f"Fallos hoy: {report.failures_today}\n"
            f"AI spend: ${report.ai_spend_today:.4f}\n"
            f"Anomalías: {len(report.anomalies)}\n"
        )
        if report.anomalies:
            system_data += "\nAnomalías:\n"
            for a in report.anomalies[:3]:
                system_data += f"  [{a.severity.value}] {a.title}\n"
        if report.recommendations:
            system_data += "\nRecomendaciones:\n"
            for r in report.recommendations:
                system_data += f"  - {r}\n"

        prompt = (
            f"Eres HERMES, el supervisor ejecutivo de IMPERIO — un sistema de affiliate marketing "
            f"que postea contenido en 6 plataformas (Telegram, Instagram, Twitter, Pinterest, TikTok, YouTube).\n\n"
            f"Estado actual del sistema:\n{system_data}\n"
            f"Historial reciente de conversación:\n{context}\n\n"
            f"Pregunta del operador: {q}\n\n"
            f"Responde en español, conciso, con datos reales. Si no tienes info suficiente, dilo."
        )

        try:
            response = await reason(prompt, max_tokens=400, temperature=0.3)
            if response and len(response) > 10:
                return response
        except Exception:
            pass

        # Fallback determinístico
        return (
            f"HERMES — Estado general:\n"
            f"  Pipeline: {report.pipeline_status}\n"
            f"  Posts: {report.posts_today} | Fallos: {report.failures_today}\n"
            f"  AI spend: ${report.ai_spend_today:.4f}\n"
            f"  Anomalías: {len(report.anomalies)}\n\n"
            f"Pregunta más específica para respuesta detallada.\n"
            f"Ej: '¿qué falló?', '¿cuánto gastamos?', '¿qué posteamos mañana?'"
        )

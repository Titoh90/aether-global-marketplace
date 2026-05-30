"""
planning_engine.py — Tactical planning based on current system state.

Generates actionable plans: what to post next, which platforms to
prioritize, when to pause, budget allocation suggestions.

Deterministic first, LLM-enhanced second.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")


@dataclass(frozen=True)
class TacticalPlan:
    timestamp: str
    next_actions: list[str]
    platform_priority: list[str]
    risk_flags: list[str]
    budget_recommendation: str
    content_suggestion: str


class PlanningEngine:
    """
    Generate tactical plans from current state.
    100% deterministic — no LLM calls.
    """

    def generate_plan(self) -> TacticalPlan:
        """Generate next-action plan based on system state."""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

        # Read state
        schedule = self._read_schedule()
        safety = self._read_safety()
        ssmie = self._read_ssmie()
        cb_state = self._read_circuit_breakers()

        # Determine platform priority
        platform_priority = self._rank_platforms(safety, cb_state)

        # Generate actions
        actions = []
        risks = []

        # Pipeline status
        if ssmie.get("system_state") == "protective_mode":
            actions.append("SSMIE en modo protectivo — reducir frecuencia de posting")
            risks.append("Sistema en modo defensivo")

        # Disabled platforms
        open_circuits = [k for k, v in cb_state.items() if v.get("state") == "OPEN"]
        if open_circuits:
            for oc in open_circuits:
                actions.append(f"Investigar executor {oc} — circuit breaker OPEN")
                risks.append(f"Plataforma {oc} deshabilitada")

        # Low health platforms — compute at runtime
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
                    actions.append(f"Pausar {_plat} — health score {_score}/100")
                    risks.append(f"{_plat} health bajo ({_score})")
                elif _score < 80:
                    actions.append(f"Reducir frecuencia en {_plat} — health {_score}/100")
        except Exception:
            pass

        # Schedule check
        if schedule.get("is_rest_day") or schedule.get("rest_day"):
            actions.append("Hoy es día de descanso — no postear")
        elif not schedule.get("posting_slots") and not schedule.get("slots"):
            actions.append("Sin slots programados — verificar stability_governor")

        # Default actions
        if not actions:
            actions.append("Sistema saludable — ejecutar pipeline normal")
            _slots = schedule.get("posting_slots") or schedule.get("slots") or []
            if _slots:
                next_slot = _slots[0]
                actions.append(f"Próximo slot: {next_slot.get('time', '?')} en {next_slot.get('platform', '?')}")

        # Budget
        budget_rec = self._budget_recommendation()

        # Content suggestion
        content = self._content_suggestion()

        return TacticalPlan(
            timestamp=timestamp,
            next_actions=actions,
            platform_priority=platform_priority,
            risk_flags=risks,
            budget_recommendation=budget_rec,
            content_suggestion=content,
        )

    def format_plan(self, plan: TacticalPlan = None) -> str:
        """Format plan as human-readable text."""
        if plan is None:
            plan = self.generate_plan()

        lines = [f"TACTICAL PLAN — {plan.timestamp}", ""]

        lines.append("Próximas acciones:")
        for a in plan.next_actions:
            lines.append(f"  - {a}")

        if plan.platform_priority:
            lines.append(f"\nPrioridad: {' > '.join(plan.platform_priority)}")

        if plan.risk_flags:
            lines.append("\nRiesgos:")
            for r in plan.risk_flags:
                lines.append(f"  ⚠ {r}")

        lines.append(f"\nBudget: {plan.budget_recommendation}")
        lines.append(f"Contenido: {plan.content_suggestion}")

        return "\n".join(lines)

    def _read_schedule(self) -> dict:
        f = IMPERIO_ROOT / "REVENUE" / "posting_schedule.json"
        if not f.exists():
            return {}
        try:
            return json.loads(f.read_text())
        except Exception:
            return {}

    def _read_safety(self) -> dict:
        f = IMPERIO_ROOT / "REVENUE" / "posting_safety.json"
        if not f.exists():
            return {}
        try:
            return json.loads(f.read_text())
        except Exception:
            return {}

    def _read_ssmie(self) -> dict:
        f = IMPERIO_ROOT / "REVENUE" / "ssmie_state.json"
        if not f.exists():
            return {}
        try:
            return json.loads(f.read_text())
        except Exception:
            return {}

    def _read_circuit_breakers(self) -> dict:
        f = IMPERIO_ROOT / "logs" / "guardrails" / "circuit_breaker_state.json"
        if not f.exists():
            return {}
        try:
            return json.loads(f.read_text())
        except Exception:
            return {}

    def _rank_platforms(self, safety: dict, cb_state: dict) -> list[str]:
        """Rank platforms by health score, excluding disabled ones."""
        open_circuits = {k for k, v in cb_state.items() if v.get("state") == "OPEN"}
        all_platforms = ["telegram", "instagram", "twitter", "pinterest", "tiktok"]
        platforms = []
        try:
            import sys as _sys
            _rev = str(IMPERIO_ROOT / "REVENUE")
            if _rev not in _sys.path:
                _sys.path.insert(0, _rev)
            from posting_safety_layer import PostingSafetyLayer
            _safety = PostingSafetyLayer()
            for plat in all_platforms:
                if plat in open_circuits:
                    continue
                health = _safety.compute_account_health(plat)
                platforms.append((plat, health.get("score", 100)))
        except Exception:
            platforms = [(p, 100) for p in all_platforms if p not in open_circuits]
        platforms.sort(key=lambda x: -x[1])
        if not platforms:
            return [p for p in all_platforms if p not in open_circuits]
        return [p[0] for p in platforms]

    def _budget_recommendation(self) -> str:
        import os
        budget = float(os.environ.get("IMPERIO_DAILY_AI_BUDGET_USD", "0") or "0")
        if budget <= 0:
            return "Sin límite configurado — monitorear manualmente"

        spend_file = IMPERIO_ROOT / "logs" / "guardrails" / f"daily_spend_{time.strftime('%Y-%m-%d')}.json"
        if not spend_file.exists():
            return f"Budget ${budget:.2f} — sin gasto registrado hoy"
        try:
            data = json.loads(spend_file.read_text())
            total = data.get("total_cost_usd", 0)
            pct = total / budget * 100
            if pct > 90:
                return f"CRITICO: ${total:.4f} ({pct:.0f}% de ${budget:.2f})"
            elif pct > 70:
                return f"ALERTA: ${total:.4f} ({pct:.0f}% de ${budget:.2f})"
            return f"OK: ${total:.4f} ({pct:.0f}% de ${budget:.2f})"
        except Exception:
            return f"Budget ${budget:.2f} — error leyendo gasto"

    def _content_suggestion(self) -> str:
        """Suggest content type based on recent posts + creative intelligence signals."""
        # Read posting schedule for content_mix
        schedule = self._read_schedule()
        content_type = schedule.get("content_type", "carousel")

        # Advisory: enrich with creative intelligence if available
        creative_hint = ""
        try:
            from core.creative_intelligence.style_rotation_engine import (
                recommend_style,
            )
            # Read campaigns directly (PlanningEngine reads JSON files, same pattern)
            cm_file = IMPERIO_ROOT / "REVENUE" / "campaigns.json"
            if cm_file.exists():
                raw = json.loads(cm_file.read_text())
                campaigns = raw.get("campaigns", raw) if isinstance(raw, dict) else {}
                for asin in list(campaigns.keys())[:1]:
                    rotation = recommend_style(asin)
                    if rotation.fatigue_level in ("high", "critical"):
                        creative_hint = (
                            f" | ⚠️ Creative: {rotation.product_name} needs rotation "
                            f"({rotation.current_style} → {rotation.recommended_style})"
                        )
                        break
        except Exception:
            pass  # Creative intelligence unavailable — not critical

        return f"Tipo sugerido: {content_type} (según stability_governor){creative_hint}"

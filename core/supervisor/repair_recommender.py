"""
repair_recommender.py — Recommend repairs for detected anomalies.

HERMES recommends but NEVER executes repairs.
All recommendations go to Telegram for human review.
"""

from __future__ import annotations

from dataclasses import dataclass
from core.supervisor.anomaly_detector import Anomaly
from core.supervisor.incident_classifier import Incident


@dataclass(frozen=True)
class RepairRecommendation:
    anomaly_id: str
    title: str
    action: str
    risk: str          # "none", "low", "medium", "high"
    auto_executable: bool  # can system execute this without human?
    command_hint: str  # suggested command or module to run


# Deterministic repair lookup — no LLM
REPAIR_MAP: dict[str, tuple[str, str, bool, str]] = {
    # anomaly_id pattern → (action, risk, auto_executable, command_hint)
    "cb_": (
        "Check platform status and session cookies. Reset circuit breaker if platform is back.",
        "low",
        False,
        "python3 -c \"from core.guardrails.circuit_breaker import CircuitBreaker; CircuitBreaker().reset('{executor}')\"",
    ),
    "budget_exhausted": (
        "Budget exhausted. Wait for next day or increase IMPERIO_DAILY_AI_BUDGET_USD.",
        "none",
        False,
        "export IMPERIO_DAILY_AI_BUDGET_USD=<new_amount>",
    ),
    "budget_warning": (
        "Approaching budget limit. Consider switching to cheaper models.",
        "none",
        True,
        "# Automatic: ai_spend_governor will downgrade tier",
    ),
    "safety_": (
        "Platform health low. Reduce posting frequency or pause platform.",
        "low",
        False,
        "/pause",
    ),
    "ssmie_protective": (
        "SSMIE protective mode active. Review ssmie_state.json for trigger.",
        "medium",
        False,
        "cat REVENUE/ssmie_state.json | python3 -m json.tool",
    ),
    "failure_spike": (
        "Multiple failures detected. Check event log for common error pattern.",
        "none",
        True,
        "python3 -c \"from core.events.event_store import EventStore; print(EventStore().recent_failures())\"",
    ),
}


def recommend_repair(anomaly: Anomaly) -> RepairRecommendation | None:
    """
    Generate repair recommendation for an anomaly.
    Returns None if no known repair exists.
    """
    for pattern, (action, risk, auto_exec, cmd) in REPAIR_MAP.items():
        if pattern in anomaly.anomaly_id:
            # Substitute executor name if present
            executor = anomaly.anomaly_id.replace("cb_", "").replace("_half", "")
            cmd_filled = cmd.replace("{executor}", executor)

            return RepairRecommendation(
                anomaly_id=anomaly.anomaly_id,
                title=f"Repair: {anomaly.title}",
                action=action,
                risk=risk,
                auto_executable=auto_exec,
                command_hint=cmd_filled,
            )

    return None


def recommend_repairs(anomalies: list[Anomaly]) -> list[RepairRecommendation]:
    """Generate recommendations for all anomalies."""
    recs = []
    for a in anomalies:
        rec = recommend_repair(a)
        if rec:
            recs.append(rec)
    return recs

"""
incident_classifier.py — Classify incidents by severity and type.

Deterministic rules first, LLM diagnosis for complex cases only.
"""

from __future__ import annotations

from dataclasses import dataclass
from core.events.event_types import Severity


@dataclass(frozen=True)
class Incident:
    incident_id: str
    title: str
    severity: Severity
    category: str       # "executor", "generation", "api", "budget", "engagement", "system"
    source_event_type: str
    details: str
    recommended_action: str
    requires_approval: bool


# Deterministic classification rules — no LLM needed
SEVERITY_RULES: list[tuple[str, Severity, str, str, bool]] = [
    # (event_type_pattern, severity, category, recommended_action, requires_approval)

    # Critical — needs human attention
    ("circuit_breaker_opened", Severity.HIGH, "executor",
     "Platform executor disabled after consecutive failures. Check platform status.",
     False),
    ("budget_exhausted", Severity.HIGH, "budget",
     "Daily AI budget exhausted. Pipeline degraded to template-only mode.",
     False),
    ("pipeline_failed", Severity.HIGH, "system",
     "Full pipeline failure. Check logs with trace_id.",
     False),

    # Medium — auto-recoverable but worth noting
    ("generation_failed", Severity.MEDIUM, "generation",
     "Content generation failed. Retry with fallback provider.",
     False),
    ("post_failed", Severity.MEDIUM, "executor",
     "Social post failed. Check executor logs and session cookies.",
     False),
    ("health_check_failed", Severity.MEDIUM, "system",
     "System health check failed. Run system_readiness.py for details.",
     False),
    ("selector_drift", Severity.MEDIUM, "generation",
     "Flow UI selector may have changed. Manual verification recommended.",
     True),

    # Low — informational
    ("budget_warning", Severity.LOW, "budget",
     "Approaching daily AI budget limit. Switching to cheaper models.",
     False),
    ("quality_gate_result", Severity.LOW, "generation",
     "Content quality score logged.",
     False),
    ("engagement_spike", Severity.LOW, "engagement",
     "Unusual engagement activity detected.",
     False),
]


def classify_incident(
    event_type: str,
    data: dict = None,
    source: str = "",
) -> Incident | None:
    """
    Classify an event into an Incident with severity and recommendation.

    Returns None if event doesn't warrant incident creation.
    """
    import uuid

    data = data or {}

    for pattern, severity, category, action, needs_approval in SEVERITY_RULES:
        if pattern in event_type:
            # Enrich details from event data
            details_parts = []
            if data.get("error"):
                details_parts.append(f"Error: {data['error'][:200]}")
            if data.get("executor"):
                details_parts.append(f"Executor: {data['executor']}")
            if data.get("platform"):
                details_parts.append(f"Platform: {data['platform']}")
            if data.get("trace_id"):
                details_parts.append(f"Trace: {data['trace_id']}")

            return Incident(
                incident_id=uuid.uuid4().hex[:10],
                title=f"{category.upper()}: {event_type.replace('_', ' ').title()}",
                severity=severity,
                category=category,
                source_event_type=event_type,
                details=" | ".join(details_parts) or "No additional details",
                recommended_action=action,
                requires_approval=needs_approval,
            )

    return None

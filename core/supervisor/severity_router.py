"""
severity_router.py — Route incidents by severity to appropriate channels.

Severity determines notification channel and response urgency:
  CRITICAL → immediate Telegram alert + approval request
  HIGH     → Telegram alert
  MEDIUM   → digest (batched every 5 min)
  LOW      → log only
  INFO     → log only
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.events.event_types import Severity
from core.supervisor.incident_classifier import Incident


class NotificationChannel(Enum):
    IMMEDIATE_ALERT = "immediate_alert"
    ALERT = "alert"
    DIGEST = "digest"
    LOG_ONLY = "log_only"


@dataclass(frozen=True)
class RoutingDecision:
    channel: NotificationChannel
    requires_approval: bool
    escalation_timeout_seconds: int  # 0 = no escalation


# Routing table
SEVERITY_ROUTES: dict[Severity, tuple[NotificationChannel, int]] = {
    Severity.CRITICAL: (NotificationChannel.IMMEDIATE_ALERT, 300),   # 5 min escalation
    Severity.HIGH:     (NotificationChannel.ALERT, 1800),            # 30 min
    Severity.MEDIUM:   (NotificationChannel.DIGEST, 0),              # no escalation
    Severity.LOW:      (NotificationChannel.LOG_ONLY, 0),
    Severity.INFO:     (NotificationChannel.LOG_ONLY, 0),
}


def route_incident(incident: Incident) -> RoutingDecision:
    """Determine notification channel for an incident."""
    channel, timeout = SEVERITY_ROUTES.get(
        incident.severity,
        (NotificationChannel.LOG_ONLY, 0),
    )

    # Override: if incident requires approval, force alert channel
    if incident.requires_approval and channel == NotificationChannel.LOG_ONLY:
        channel = NotificationChannel.ALERT

    return RoutingDecision(
        channel=channel,
        requires_approval=incident.requires_approval,
        escalation_timeout_seconds=timeout,
    )


def route_incidents(incidents: list[Incident]) -> dict[NotificationChannel, list[Incident]]:
    """Group incidents by their routed channel."""
    groups: dict[NotificationChannel, list[Incident]] = {}
    for inc in incidents:
        decision = route_incident(inc)
        groups.setdefault(decision.channel, []).append(inc)
    return groups

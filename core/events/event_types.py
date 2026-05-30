"""
event_types.py — Canonical event type definitions for IMPERIO event bus.

Every cross-module event in the system is one of these types.
Frozen enum — add new types here, never remove existing ones.
"""

from __future__ import annotations

from enum import Enum


class EventType(str, Enum):
    # Pipeline lifecycle
    PIPELINE_STARTED = "pipeline_started"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_FAILED = "pipeline_failed"

    # Content generation
    GENERATION_STARTED = "generation_started"
    GENERATION_COMPLETED = "generation_completed"
    GENERATION_FAILED = "generation_failed"
    QUALITY_GATE_RESULT = "quality_gate_result"

    # Social posting
    POST_PUBLISHED = "post_published"
    POST_FAILED = "post_failed"

    # Engagement
    COMMENT_RECEIVED = "comment_received"
    REPLY_SENT = "reply_sent"
    ENGAGEMENT_SPIKE = "engagement_spike"

    # System health
    CIRCUIT_BREAKER_OPENED = "circuit_breaker_opened"
    CIRCUIT_BREAKER_CLOSED = "circuit_breaker_closed"
    BUDGET_WARNING = "budget_warning"
    BUDGET_EXHAUSTED = "budget_exhausted"
    HEALTH_CHECK_FAILED = "health_check_failed"

    # Flow / visual
    SELECTOR_DRIFT = "selector_drift"
    FLOW_UI_CHANGED = "flow_ui_changed"

    # Revenue
    CLICK_TRACKED = "click_tracked"
    SALE_RECORDED = "sale_recorded"

    # Supervisor
    INCIDENT_DETECTED = "incident_detected"
    INCIDENT_RESOLVED = "incident_resolved"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_DENIED = "approval_denied"
    APPROVAL_EXPIRED = "approval_expired"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

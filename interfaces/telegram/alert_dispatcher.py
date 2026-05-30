"""
alert_dispatcher.py — Dispatch alerts from supervisor to Telegram.

Connects event bus to Telegram notifications. Filters by severity
to avoid alert fatigue. Rate-limits repeated alerts.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field

from core.events.event_bus import bus, Event
from core.events.event_types import EventType, Severity

log = logging.getLogger("hermes.alerts")

# Minimum severity to send Telegram alert
ALERT_THRESHOLD = Severity.MEDIUM

# Rate limit: max 1 alert per event_type per N seconds
RATE_LIMIT_SECONDS = 300  # 5 minutes


@dataclass
class AlertDispatcher:
    """
    Watches event bus for high-severity events and dispatches
    to Telegram via the bot instance.

    Rate-limits to prevent alert fatigue.
    """
    _last_alert: dict = field(default_factory=dict)  # {event_type: timestamp}
    _bot: object = None  # HermesTelegramBot — set via connect()
    _enabled: bool = True

    def connect(self, bot):
        """Connect to Telegram bot instance for sending."""
        self._bot = bot

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    def should_alert(self, event: Event) -> bool:
        """Check if event warrants a Telegram alert."""
        if not self._enabled:
            return False

        # Check severity threshold
        sev_order = {
            Severity.INFO: 0, Severity.LOW: 1, Severity.MEDIUM: 2,
            Severity.HIGH: 3, Severity.CRITICAL: 4,
        }
        if sev_order.get(event.severity, 0) < sev_order.get(ALERT_THRESHOLD, 2):
            return False

        # Rate limit check
        et_key = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
        now = time.time()
        last = self._last_alert.get(et_key, 0)
        if now - last < RATE_LIMIT_SECONDS:
            return False

        return True

    async def dispatch(self, event: Event):
        """Send alert for event if it passes filters."""
        if not self.should_alert(event):
            return

        if not self._bot:
            log.warning("Alert dispatcher has no bot connected")
            return

        # Update rate limit
        et_key = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
        self._last_alert[et_key] = time.time()

        # Format alert
        sev_str = event.severity.value if hasattr(event.severity, 'value') else str(event.severity)
        title = et_key.replace("_", " ").title()

        body_parts = []
        if event.data.get("error"):
            body_parts.append(f"Error: {event.data['error'][:200]}")
        if event.data.get("executor"):
            body_parts.append(f"Executor: {event.data['executor']}")
        if event.data.get("platform"):
            body_parts.append(f"Platform: {event.data['platform']}")
        if event.trace_id:
            body_parts.append(f"Trace: {event.trace_id}")

        body = "\n".join(body_parts) or "Sin detalles adicionales."

        await self._bot.send_alert(
            title=title,
            body=body,
            severity=sev_str,
        )

    def register_handlers(self):
        """Register on event bus for alertable event types."""
        # Only register for events that can be HIGH/CRITICAL
        alert_types = [
            EventType.PIPELINE_FAILED,
            EventType.POST_FAILED,
            EventType.GENERATION_FAILED,
            EventType.CIRCUIT_BREAKER_OPENED,
            EventType.BUDGET_EXHAUSTED,
            EventType.HEALTH_CHECK_FAILED,
        ]
        for et in alert_types:
            bus.on(et, self._sync_handler)

    def _sync_handler(self, event: Event):
        """Sync wrapper — queues async dispatch."""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.dispatch(event))
        except RuntimeError:
            # No running loop — log instead
            if self.should_alert(event):
                et_key = event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type)
                log.warning(f"Alert (no loop): [{event.severity.value}] {et_key}")


# Singleton
_dispatcher: AlertDispatcher | None = None


def get_dispatcher() -> AlertDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = AlertDispatcher()
    return _dispatcher

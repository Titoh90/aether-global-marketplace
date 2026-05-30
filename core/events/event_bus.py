"""
event_bus.py — Lightweight in-process event bus for IMPERIO.

Publish-subscribe pattern. Handlers registered per EventType.
Events are also persisted to JSONL (via event_store) for replay.

Usage:
    from core.events.event_bus import bus, emit

    # Subscribe
    bus.on(EventType.POST_PUBLISHED, my_handler)

    # Emit
    emit(EventType.POST_PUBLISHED, {"platform": "instagram", "media_id": "123"})

Thread-safe. Non-blocking handlers (exceptions logged, never propagate).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable

from core.events.event_types import EventType, Severity

log = logging.getLogger("event_bus")

# Try to import correlation for trace_id
try:
    from core.observability.correlation import get_current_trace
except ImportError:
    def get_current_trace():
        return None


@dataclass(frozen=True)
class Event:
    event_id: str
    event_type: EventType
    severity: Severity
    timestamp: str
    trace_id: str
    data: dict
    source: str


# Handler type: receives Event, returns None
EventHandler = Callable[[Event], None]


class EventBus:
    """In-process pub/sub event bus. Thread-safe."""

    def __init__(self):
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._lock = Lock()
        self._store = None  # lazy-loaded

    def on(self, event_type: EventType, handler: EventHandler) -> None:
        """Register handler for event type."""
        with self._lock:
            self._handlers[event_type].append(handler)

    def off(self, event_type: EventType, handler: EventHandler) -> None:
        """Unregister handler."""
        with self._lock:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    def emit(self, event: Event) -> None:
        """Dispatch event to all registered handlers. Non-blocking."""
        # Persist to store first
        self._persist(event)

        # Call handlers
        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                log.error(f"Handler error for {event.event_type}: {e}")

    def _persist(self, event: Event) -> None:
        """Persist event to JSONL store."""
        if self._store is None:
            try:
                from core.events.event_store import EventStore
                self._store = EventStore()
            except Exception:
                return
        try:
            self._store.append(event)
        except Exception as e:
            log.error(f"Event store error: {e}")

    def handler_count(self, event_type: EventType) -> int:
        with self._lock:
            return len(self._handlers.get(event_type, []))


# Singleton bus instance
bus = EventBus()


def emit(
    event_type: EventType | str,
    data: dict = None,
    severity: Severity | str = Severity.INFO,
    source: str = "",
) -> Event:
    """
    Convenience function to create and emit an event.

    Args:
        event_type: EventType enum or string
        data: event payload
        severity: Severity enum or string
        source: module/component name

    Returns:
        The emitted Event object
    """
    if isinstance(event_type, str):
        try:
            event_type = EventType(event_type)
        except ValueError:
            event_type = EventType.PIPELINE_STARTED  # fallback

    if isinstance(severity, str):
        try:
            severity = Severity(severity)
        except ValueError:
            severity = Severity.INFO

    event = Event(
        event_id=uuid.uuid4().hex[:12],
        event_type=event_type,
        severity=severity,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        trace_id=get_current_trace() or "",
        data=data or {},
        source=source,
    )
    bus.emit(event)
    return event

#!/usr/bin/env python3
"""
provider_health.py — In-memory health tracking for LLM providers.

Marks providers as unhealthy for COOLDOWN_SECONDS after a failure.
Thread-safe via threading.Lock.
"""

from __future__ import annotations

import threading
import time

COOLDOWN_SECONDS = 60  # provider stays unhealthy this long after failure

_lock   = threading.Lock()
_state: dict[str, dict] = {}  # provider_id -> {failed_at, error}


def mark_healthy(provider_id: str) -> None:
    with _lock:
        _state.pop(provider_id, None)


def mark_failed(provider_id: str, error: str = "") -> None:
    with _lock:
        _state[provider_id] = {"failed_at": time.monotonic(), "error": error}


def is_healthy(provider_id: str) -> bool:
    with _lock:
        entry = _state.get(provider_id)
        if entry is None:
            return True
        elapsed = time.monotonic() - entry["failed_at"]
        if elapsed >= COOLDOWN_SECONDS:
            del _state[provider_id]
            return True
        return False


def get_status() -> dict[str, dict]:
    """Return copy of current health state."""
    with _lock:
        return dict(_state)

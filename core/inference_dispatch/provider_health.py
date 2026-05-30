#!/usr/bin/env python3
"""
provider_health.py — Provider health tracking with persistent JSONL failover log.

Extends core/llm/provider_health.py with:
- Persistent logging to logs/inference_failover/YYYY-MM-DD.jsonl
- FailoverEvent schema
- Task-type aware failure logging

Thread-safe via threading.Lock.
"""

from __future__ import annotations

import datetime
import json
import sys
import threading
import time
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.inference_dispatch.schemas import FailoverEvent

_LOG_DIR = _IMPERIO_ROOT / "logs" / "inference_failover"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

COOLDOWN_SECONDS = 120  # longer than core/llm (60s) — inference is more expensive

_lock:   threading.Lock      = threading.Lock()
_state:  dict[str, dict]     = {}  # provider_id → {failed_at, error, task_type}


# ── Health tracking ───────────────────────────────────────────────────────────

def mark_healthy(provider_id: str) -> None:
    with _lock:
        _state.pop(provider_id, None)


def mark_failed(provider_id: str, error: str = "", task_type: str = "") -> None:
    with _lock:
        _state[provider_id] = {
            "failed_at": time.monotonic(),
            "error":     error[:200],
            "task_type": task_type,
        }


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
    """Return copy of current in-memory health state."""
    with _lock:
        return dict(_state)


# ── Failover logging ──────────────────────────────────────────────────────────

def log_failover_event(event: FailoverEvent) -> None:
    """
    Append a FailoverEvent to today's JSONL log.
    Append-only — never mutates existing entries.
    Silent on write failure (never blocks inference).
    """
    try:
        date_str  = datetime.date.today().isoformat()
        log_file  = _LOG_DIR / f"{date_str}.jsonl"
        entry = {
            "ts":             event.ts,
            "task_type":      event.task_type,
            "task_id":        event.task_id,
            "provider_tried": event.provider_tried,
            "model_tried":    event.model_tried,
            "error":          event.error[:200],
            "fallback_to":    event.fallback_to,
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # failover logging is best-effort — never block inference


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def emit_failover(
    task_type: str,
    task_id: str,
    provider_tried: str,
    model_tried: str,
    error: str,
    fallback_to: str,
) -> None:
    """Convenience wrapper: create + log FailoverEvent + mark_failed."""
    event = FailoverEvent(
        ts=_now_iso(),
        task_type=task_type,
        task_id=task_id,
        provider_tried=provider_tried,
        model_tried=model_tried,
        error=error[:200],
        fallback_to=fallback_to,
    )
    mark_failed(provider_id=provider_tried, error=error, task_type=task_type)
    log_failover_event(event)

"""
correlation.py — Pipeline trace ID for cross-module log correlation.

Generates and propagates a trace_id per pipeline run so every log entry
(LLM calls, dispatch, executor, events) can be linked to one execution.

Usage:
    # At pipeline start (master_pipeline.py or launch_daily.sh via env):
    from core.observability.correlation import new_trace, get_current_trace
    new_trace()  # generates + sets thread-local trace_id

    # In any module that logs:
    trace_id = get_current_trace() or "no-trace"
    log_entry["trace_id"] = trace_id
"""

from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone

_local = threading.local()


def new_trace() -> str:
    """Generate a new trace_id and set it as current. Returns the trace_id."""
    # Check env var first (set by launch_daily.sh)
    tid = os.environ.get("IMPERIO_TRACE_ID", "")
    if not tid:
        tid = uuid.uuid4().hex[:16]
    _local.trace_id = tid
    _local.started_at = datetime.now(timezone.utc).isoformat()
    return tid


def get_current_trace() -> str | None:
    """Get current trace_id for this thread. Returns None if not set."""
    return getattr(_local, "trace_id", None)


def set_current_trace(trace_id: str) -> None:
    """Manually set trace_id (e.g. from env var or parent process)."""
    _local.trace_id = trace_id


def trace_context() -> dict:
    """Return dict with trace metadata for inclusion in log entries."""
    return {
        "trace_id": getattr(_local, "trace_id", None),
        "started_at": getattr(_local, "started_at", None),
    }

"""
event_store.py — Append-only JSONL persistence for events.

Stores all events to daily JSONL files. Supports querying by type,
severity, time range, and trace_id for replay/debug.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Lock

from core.events.event_types import EventType, Severity

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
EVENTS_DIR = IMPERIO_ROOT / "logs" / "events"


class EventStore:
    """Append-only event persistence to daily JSONL files."""

    def __init__(self, events_dir: Path = EVENTS_DIR):
        self._dir = events_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def _today_file(self) -> Path:
        return self._dir / f"{time.strftime('%Y-%m-%d')}.jsonl"

    def append(self, event) -> None:
        """Persist event to today's JSONL file."""
        with self._lock:
            entry = {
                "event_id": event.event_id,
                "event_type": event.event_type.value if hasattr(event.event_type, 'value') else str(event.event_type),
                "severity": event.severity.value if hasattr(event.severity, 'value') else str(event.severity),
                "timestamp": event.timestamp,
                "trace_id": event.trace_id,
                "data": event.data,
                "source": event.source,
            }
            with open(self._today_file(), "a") as f:
                f.write(json.dumps(entry) + "\n")

    def query(
        self,
        event_type: EventType | str = None,
        severity: Severity | str = None,
        trace_id: str = None,
        date: str = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Query events from JSONL files.

        Args:
            event_type: filter by type
            severity: filter by minimum severity
            trace_id: filter by trace_id
            date: specific date (YYYY-MM-DD), default today
            limit: max results

        Returns:
            List of event dicts, newest first
        """
        target = date or time.strftime("%Y-%m-%d")
        fpath = self._dir / f"{target}.jsonl"
        if not fpath.exists():
            return []

        severity_order = ["info", "low", "medium", "high", "critical"]
        min_sev_idx = 0
        if severity:
            sev_val = severity.value if hasattr(severity, 'value') else str(severity)
            min_sev_idx = severity_order.index(sev_val) if sev_val in severity_order else 0

        results = []
        try:
            with open(fpath) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Apply filters
                    if event_type:
                        et_val = event_type.value if hasattr(event_type, 'value') else str(event_type)
                        if entry.get("event_type") != et_val:
                            continue
                    if severity:
                        entry_sev = entry.get("severity", "info")
                        if severity_order.index(entry_sev) if entry_sev in severity_order else 0 < min_sev_idx:
                            continue
                    if trace_id and entry.get("trace_id") != trace_id:
                        continue

                    results.append(entry)
        except Exception:
            pass

        # Newest first, limited
        results.reverse()
        return results[:limit]

    def count_by_type(self, date: str = None) -> dict[str, int]:
        """Count events by type for a given date."""
        events = self.query(date=date, limit=10000)
        counts: dict[str, int] = {}
        for e in events:
            et = e.get("event_type", "unknown")
            counts[et] = counts.get(et, 0) + 1
        return counts

    def recent_failures(self, limit: int = 10, date: str = None) -> list[dict]:
        """Get recent failure events."""
        all_events = self.query(date=date, limit=10000)
        failures = [
            e for e in all_events
            if "failed" in e.get("event_type", "")
            or e.get("severity") in ("high", "critical")
        ]
        return failures[:limit]

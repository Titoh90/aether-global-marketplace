"""
task_quarantine.py — Quarantine failed tasks for later inspection.

When a task fails repeatedly or an executor is disabled, the task
is moved to quarantine instead of being discarded. Quarantined tasks
can be retried after the root cause is fixed.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
QUARANTINE_FILE = IMPERIO_ROOT / "logs" / "guardrails" / "quarantine.jsonl"


@dataclass(frozen=True)
class QuarantinedTask:
    task_id: str
    task_type: str       # "post", "generation", "engagement"
    platform: str
    reason: str
    data: dict
    quarantined_at: str
    attempts: int
    last_error: str


class TaskQuarantine:
    """Manage quarantined tasks."""

    def __init__(self):
        QUARANTINE_FILE.parent.mkdir(parents=True, exist_ok=True)

    def quarantine(
        self,
        task_id: str,
        task_type: str,
        platform: str,
        reason: str,
        data: dict = None,
        attempts: int = 0,
        last_error: str = "",
    ) -> QuarantinedTask:
        """Add task to quarantine."""
        task = QuarantinedTask(
            task_id=task_id,
            task_type=task_type,
            platform=platform,
            reason=reason,
            data=data or {},
            quarantined_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            attempts=attempts,
            last_error=last_error[:500],
        )

        entry = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "platform": task.platform,
            "reason": task.reason,
            "data": task.data,
            "quarantined_at": task.quarantined_at,
            "attempts": task.attempts,
            "last_error": task.last_error,
        }

        with open(QUARANTINE_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")

        return task

    def get_quarantined(self, platform: str = None, limit: int = 20) -> list[dict]:
        """Read quarantined tasks, optionally filtered by platform."""
        if not QUARANTINE_FILE.exists():
            return []

        tasks = []
        try:
            with open(QUARANTINE_FILE) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if platform and entry.get("platform") != platform:
                            continue
                        tasks.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass

        return tasks[-limit:]

    def count(self, platform: str = None) -> int:
        """Count quarantined tasks."""
        return len(self.get_quarantined(platform=platform, limit=10000))

    def clear(self, platform: str = None):
        """Clear quarantine. If platform specified, only clear that platform."""
        if platform is None:
            # Clear all
            if QUARANTINE_FILE.exists():
                QUARANTINE_FILE.write_text("")
            return

        # Keep tasks from other platforms
        remaining = []
        if QUARANTINE_FILE.exists():
            try:
                with open(QUARANTINE_FILE) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if entry.get("platform") != platform:
                                remaining.append(line)
                        except json.JSONDecodeError:
                            remaining.append(line)
            except Exception:
                pass

        QUARANTINE_FILE.write_text("\n".join(remaining) + "\n" if remaining else "")

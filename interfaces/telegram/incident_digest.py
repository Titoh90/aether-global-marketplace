"""
incident_digest.py — Aggregate incidents into periodic digests.

Instead of alerting on every incident individually, collects
incidents over a window and sends a single digest message.
Reduces noise while maintaining visibility.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from core.supervisor.incident_classifier import Incident


@dataclass
class IncidentDigest:
    """
    Collect incidents and produce periodic digest messages.

    Usage:
        digest = IncidentDigest(window_seconds=300)
        digest.add(incident)
        ...
        if digest.is_ready():
            msg = digest.flush()
            # send msg to Telegram
    """
    window_seconds: int = 300  # 5 minute digest window
    _incidents: list[Incident] = field(default_factory=list)
    _window_start: float = field(default_factory=time.time)

    def add(self, incident: Incident):
        """Add incident to current digest window."""
        self._incidents.append(incident)

    def is_ready(self) -> bool:
        """Check if digest window has elapsed and there are incidents."""
        if not self._incidents:
            return False
        return (time.time() - self._window_start) >= self.window_seconds

    def flush(self) -> str:
        """
        Format and clear the current digest window.
        Returns formatted message for Telegram.
        """
        if not self._incidents:
            return ""

        # Group by severity
        by_severity: dict[str, list[Incident]] = {}
        for inc in self._incidents:
            sev = inc.severity.value
            by_severity.setdefault(sev, []).append(inc)

        lines = [
            f"INCIDENT DIGEST ({len(self._incidents)} incidents)",
            f"Window: {int(time.time() - self._window_start)}s",
            "",
        ]

        sev_order = ["critical", "high", "medium", "low", "info"]
        for sev in sev_order:
            incidents = by_severity.get(sev, [])
            if not incidents:
                continue

            icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "⚪"}.get(sev, "")
            lines.append(f"{icon} {sev.upper()} ({len(incidents)}):")
            for inc in incidents[:5]:  # cap per severity
                lines.append(f"  {inc.title}")
                if inc.requires_approval:
                    lines.append(f"    /approve {inc.incident_id}")

            if len(incidents) > 5:
                lines.append(f"  ... +{len(incidents) - 5} more")

        # Reset window
        self._incidents = []
        self._window_start = time.time()

        return "\n".join(lines)

    @property
    def pending_count(self) -> int:
        return len(self._incidents)

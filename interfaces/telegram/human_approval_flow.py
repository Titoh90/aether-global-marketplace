"""
human_approval_flow.py — Manage human-in-the-loop approval workflows.

When HERMES detects an incident that requires human approval
(e.g., posting outside schedule, expanding product categories),
this module tracks the request lifecycle:

  1. Request created → sent to Telegram
  2. Pending → waiting for /approve or /reject
  3. Approved/Rejected → logged, action dispatched or cancelled
  4. Expired → auto-rejected after timeout

HERMES NEVER executes approved actions directly.
It emits an event that the appropriate subsystem can act on.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from core.events.event_bus import emit
from core.events.event_types import EventType, Severity

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
APPROVAL_LOG = IMPERIO_ROOT / "logs" / "approvals.jsonl"
APPROVAL_STATE = IMPERIO_ROOT / "logs" / "guardrails" / "pending_approvals.json"

# Auto-expire pending approvals after 2 hours
APPROVAL_TIMEOUT_SECONDS = 7200


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True)
class ApprovalRequest:
    request_id: str
    incident_id: str
    title: str
    details: str
    recommended_action: str
    category: str          # "posting", "expansion", "override"
    created_at: float
    status: ApprovalStatus = ApprovalStatus.PENDING


class HumanApprovalFlow:
    """
    Track approval requests through their lifecycle.

    Persists state to disk so approvals survive bot restarts.
    """

    def __init__(self):
        self._pending: dict[str, ApprovalRequest] = {}
        APPROVAL_LOG.parent.mkdir(parents=True, exist_ok=True)
        APPROVAL_STATE.parent.mkdir(parents=True, exist_ok=True)
        self._load_state()

    def create_request(
        self,
        incident_id: str,
        title: str,
        details: str,
        recommended_action: str,
        category: str = "system",
    ) -> ApprovalRequest:
        """Create a new approval request."""
        import uuid
        request_id = uuid.uuid4().hex[:10]

        request = ApprovalRequest(
            request_id=request_id,
            incident_id=incident_id,
            title=title,
            details=details,
            recommended_action=recommended_action,
            category=category,
            created_at=time.time(),
        )

        self._pending[request_id] = request
        self._save_state()
        self._log_event(request, "created")

        return request

    def approve(self, request_id: str) -> ApprovalRequest | None:
        """Approve a pending request."""
        req = self._pending.get(request_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return None

        approved = ApprovalRequest(
            request_id=req.request_id,
            incident_id=req.incident_id,
            title=req.title,
            details=req.details,
            recommended_action=req.recommended_action,
            category=req.category,
            created_at=req.created_at,
            status=ApprovalStatus.APPROVED,
        )

        self._pending[request_id] = approved
        self._save_state()
        self._log_event(approved, "approved")

        # Emit approval event for downstream systems
        emit(
            EventType.APPROVAL_GRANTED,
            data={
                "request_id": request_id,
                "incident_id": req.incident_id,
                "action": req.recommended_action,
                "category": req.category,
            },
            severity=Severity.INFO,
            source="human_approval_flow",
        )

        return approved

    def reject(self, request_id: str) -> ApprovalRequest | None:
        """Reject a pending request."""
        req = self._pending.get(request_id)
        if not req or req.status != ApprovalStatus.PENDING:
            return None

        rejected = ApprovalRequest(
            request_id=req.request_id,
            incident_id=req.incident_id,
            title=req.title,
            details=req.details,
            recommended_action=req.recommended_action,
            category=req.category,
            created_at=req.created_at,
            status=ApprovalStatus.REJECTED,
        )

        self._pending[request_id] = rejected
        self._save_state()
        self._log_event(rejected, "rejected")

        return rejected

    def expire_stale(self) -> list[ApprovalRequest]:
        """Expire requests older than timeout. Returns expired list."""
        now = time.time()
        expired = []

        for rid, req in list(self._pending.items()):
            if req.status != ApprovalStatus.PENDING:
                continue
            if now - req.created_at > APPROVAL_TIMEOUT_SECONDS:
                exp = ApprovalRequest(
                    request_id=req.request_id,
                    incident_id=req.incident_id,
                    title=req.title,
                    details=req.details,
                    recommended_action=req.recommended_action,
                    category=req.category,
                    created_at=req.created_at,
                    status=ApprovalStatus.EXPIRED,
                )
                self._pending[rid] = exp
                expired.append(exp)
                self._log_event(exp, "expired")

        if expired:
            self._save_state()
        return expired

    def get_pending(self) -> list[ApprovalRequest]:
        """Get all pending requests."""
        return [r for r in self._pending.values() if r.status == ApprovalStatus.PENDING]

    def _log_event(self, req: ApprovalRequest, action: str):
        """Append to approval log."""
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "request_id": req.request_id,
            "incident_id": req.incident_id,
            "action": action,
            "title": req.title,
            "category": req.category,
        }
        try:
            with open(APPROVAL_LOG, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def _save_state(self):
        """Persist pending approvals to disk."""
        state = {}
        for rid, req in self._pending.items():
            state[rid] = {
                "request_id": req.request_id,
                "incident_id": req.incident_id,
                "title": req.title,
                "details": req.details,
                "recommended_action": req.recommended_action,
                "category": req.category,
                "created_at": req.created_at,
                "status": req.status.value,
            }
        try:
            APPROVAL_STATE.write_text(json.dumps(state, indent=2))
        except Exception:
            pass

    def _load_state(self):
        """Load persisted approvals from disk."""
        if not APPROVAL_STATE.exists():
            return
        try:
            state = json.loads(APPROVAL_STATE.read_text())
            for rid, data in state.items():
                self._pending[rid] = ApprovalRequest(
                    request_id=data["request_id"],
                    incident_id=data["incident_id"],
                    title=data["title"],
                    details=data["details"],
                    recommended_action=data["recommended_action"],
                    category=data["category"],
                    created_at=data["created_at"],
                    status=ApprovalStatus(data.get("status", "pending")),
                )
        except Exception:
            pass

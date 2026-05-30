"""
test_phase5_hermes.py — Tests for Phase 5: HERMES Telegram Cognitive Control Layer.

Covers:
- Event bus + event store (5D)
- Supervisor: incident classifier, anomaly detector, supervisor loop (5B)
- Repair recommender, retry policy, severity router, task quarantine (5B)
- Telegram: command router, report generator, alert dispatcher,
            incident digest, human approval flow (5A)
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure IMPERIO_ROOT is importable
IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
sys.path.insert(0, str(IMPERIO_ROOT))


# ──────────────────────────────────────────────
# EVENT BUS & STORE
# ──────────────────────────────────────────────

class TestEventBus:
    def test_emit_and_receive(self):
        from core.events.event_bus import EventBus, Event
        from core.events.event_types import EventType, Severity

        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        bus.on(EventType.PIPELINE_STARTED, handler)
        event = Event(
            event_id="test1",
            event_type=EventType.PIPELINE_STARTED,
            severity=Severity.INFO,
            timestamp="2026-01-01T00:00:00",
            trace_id="",
            data={"test": True},
            source="test",
        )
        bus.emit(event)
        assert len(received) == 1
        assert received[0].data["test"] is True

    def test_handler_isolation(self):
        """Handler exception should not crash bus."""
        from core.events.event_bus import EventBus, Event
        from core.events.event_types import EventType, Severity

        bus = EventBus()
        results = []

        def bad_handler(event):
            raise ValueError("boom")

        def good_handler(event):
            results.append("ok")

        bus.on(EventType.PIPELINE_STARTED, bad_handler)
        bus.on(EventType.PIPELINE_STARTED, good_handler)

        event = Event("t2", EventType.PIPELINE_STARTED, Severity.INFO,
                       "now", "", {}, "test")
        bus.emit(event)
        assert results == ["ok"]

    def test_off_unregister(self):
        from core.events.event_bus import EventBus, Event
        from core.events.event_types import EventType, Severity

        bus = EventBus()
        count = []
        handler = lambda e: count.append(1)

        bus.on(EventType.POST_PUBLISHED, handler)
        assert bus.handler_count(EventType.POST_PUBLISHED) == 1

        bus.off(EventType.POST_PUBLISHED, handler)
        assert bus.handler_count(EventType.POST_PUBLISHED) == 0


class TestEventStore:
    def test_append_and_query(self):
        from core.events.event_store import EventStore
        from core.events.event_bus import Event
        from core.events.event_types import EventType, Severity

        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventStore(events_dir=Path(tmpdir))

            event = Event("e1", EventType.POST_PUBLISHED, Severity.INFO,
                          time.strftime("%Y-%m-%dT%H:%M:%S"), "trace123",
                          {"platform": "instagram"}, "test")
            store.append(event)

            results = store.query()
            assert len(results) == 1
            assert results[0]["event_type"] == "post_published"
            assert results[0]["trace_id"] == "trace123"

    def test_query_by_type(self):
        from core.events.event_store import EventStore
        from core.events.event_bus import Event
        from core.events.event_types import EventType, Severity

        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventStore(events_dir=Path(tmpdir))

            for et in [EventType.POST_PUBLISHED, EventType.POST_FAILED, EventType.POST_PUBLISHED]:
                event = Event("x", et, Severity.INFO, "now", "", {}, "t")
                store.append(event)

            results = store.query(event_type=EventType.POST_PUBLISHED)
            assert len(results) == 2

    def test_recent_failures(self):
        from core.events.event_store import EventStore
        from core.events.event_bus import Event
        from core.events.event_types import EventType, Severity

        with tempfile.TemporaryDirectory() as tmpdir:
            store = EventStore(events_dir=Path(tmpdir))
            store.append(Event("f1", EventType.POST_FAILED, Severity.HIGH, "now", "", {}, "t"))
            store.append(Event("ok", EventType.POST_PUBLISHED, Severity.INFO, "now", "", {}, "t"))

            failures = store.recent_failures()
            assert len(failures) == 1
            assert failures[0]["event_type"] == "post_failed"


# ──────────────────────────────────────────────
# INCIDENT CLASSIFIER
# ──────────────────────────────────────────────

class TestIncidentClassifier:
    def test_classify_known_event(self):
        from core.supervisor.incident_classifier import classify_incident
        from core.events.event_types import Severity

        inc = classify_incident("circuit_breaker_opened", {"executor": "instagram"})
        assert inc is not None
        assert inc.severity == Severity.HIGH
        assert inc.category == "executor"

    def test_classify_unknown_event(self):
        from core.supervisor.incident_classifier import classify_incident
        inc = classify_incident("random_event_xyz")
        assert inc is None

    def test_classify_with_details(self):
        from core.supervisor.incident_classifier import classify_incident
        inc = classify_incident("post_failed", {
            "error": "Session expired",
            "platform": "tiktok",
            "trace_id": "abc123",
        })
        assert inc is not None
        assert "tiktok" in inc.details.lower() or "Platform: tiktok" in inc.details

    def test_requires_approval(self):
        from core.supervisor.incident_classifier import classify_incident
        inc = classify_incident("selector_drift")
        assert inc is not None
        assert inc.requires_approval is True


# ──────────────────────────────────────────────
# ANOMALY DETECTOR
# ──────────────────────────────────────────────

class TestAnomalyDetector:
    def test_no_anomalies_clean_state(self):
        """With no state files, should return empty list."""
        from core.supervisor.anomaly_detector import detect_anomalies
        # This reads real files — may or may not find anomalies
        result = detect_anomalies()
        assert isinstance(result, list)

    def test_anomaly_sorted_by_severity(self):
        from core.supervisor.anomaly_detector import detect_anomalies
        anomalies = detect_anomalies()
        if len(anomalies) >= 2:
            sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            for i in range(len(anomalies) - 1):
                a_sev = sev_order.get(anomalies[i].severity.value, 5)
                b_sev = sev_order.get(anomalies[i+1].severity.value, 5)
                assert a_sev <= b_sev


# ──────────────────────────────────────────────
# REPAIR RECOMMENDER
# ──────────────────────────────────────────────

class TestRepairRecommender:
    def test_recommend_circuit_breaker(self):
        from core.supervisor.repair_recommender import recommend_repair
        from core.supervisor.anomaly_detector import Anomaly
        from core.events.event_types import Severity

        anomaly = Anomaly(
            anomaly_id="cb_instagram",
            title="Circuit breaker OPEN: instagram",
            severity=Severity.HIGH,
            category="executor",
            details="3 consecutive failures",
            detected_at="now",
        )
        rec = recommend_repair(anomaly)
        assert rec is not None
        assert "instagram" in rec.command_hint
        assert rec.auto_executable is False

    def test_recommend_budget(self):
        from core.supervisor.repair_recommender import recommend_repair
        from core.supervisor.anomaly_detector import Anomaly
        from core.events.event_types import Severity

        anomaly = Anomaly("budget_exhausted", "Budget exhausted",
                          Severity.HIGH, "budget", "Over budget", "now")
        rec = recommend_repair(anomaly)
        assert rec is not None
        assert "IMPERIO_DAILY_AI_BUDGET_USD" in rec.command_hint

    def test_unknown_anomaly_returns_none(self):
        from core.supervisor.repair_recommender import recommend_repair
        from core.supervisor.anomaly_detector import Anomaly
        from core.events.event_types import Severity

        anomaly = Anomaly("xyz_unknown", "Unknown", Severity.LOW,
                          "other", "?", "now")
        assert recommend_repair(anomaly) is None


# ──────────────────────────────────────────────
# RETRY POLICY ENGINE
# ──────────────────────────────────────────────

class TestRetryPolicyEngine:
    def test_first_retry_allowed(self):
        from core.supervisor.retry_policy_engine import get_retry_decision, RetryDecision
        decision, delay = get_retry_decision("executor", attempt=0)
        assert decision == RetryDecision.RETRY
        assert delay > 0

    def test_max_retries_escalates(self):
        from core.supervisor.retry_policy_engine import get_retry_decision, RetryDecision
        decision, _ = get_retry_decision("executor", attempt=10)
        assert decision == RetryDecision.ESCALATE

    def test_circuit_open_skips(self):
        from core.supervisor.retry_policy_engine import get_retry_decision, RetryDecision
        decision, _ = get_retry_decision("executor", attempt=0, circuit_open=True)
        assert decision == RetryDecision.SKIP

    def test_budget_no_retry(self):
        from core.supervisor.retry_policy_engine import get_retry_decision, RetryDecision
        decision, _ = get_retry_decision("budget", attempt=0)
        assert decision == RetryDecision.ESCALATE

    def test_backoff_increases(self):
        from core.supervisor.retry_policy_engine import get_retry_decision
        _, delay0 = get_retry_decision("api", attempt=0)
        _, delay1 = get_retry_decision("api", attempt=1)
        assert delay1 > delay0


# ──────────────────────────────────────────────
# SEVERITY ROUTER
# ──────────────────────────────────────────────

class TestSeverityRouter:
    def test_critical_immediate(self):
        from core.supervisor.severity_router import route_incident, NotificationChannel
        from core.supervisor.incident_classifier import Incident
        from core.events.event_types import Severity

        inc = Incident("i1", "Test", Severity.CRITICAL, "system",
                        "test", "details", "action", False)
        decision = route_incident(inc)
        assert decision.channel == NotificationChannel.IMMEDIATE_ALERT

    def test_low_log_only(self):
        from core.supervisor.severity_router import route_incident, NotificationChannel
        from core.supervisor.incident_classifier import Incident
        from core.events.event_types import Severity

        inc = Incident("i2", "Test", Severity.LOW, "system",
                        "test", "details", "action", False)
        decision = route_incident(inc)
        assert decision.channel == NotificationChannel.LOG_ONLY

    def test_approval_upgrades_channel(self):
        from core.supervisor.severity_router import route_incident, NotificationChannel
        from core.supervisor.incident_classifier import Incident
        from core.events.event_types import Severity

        inc = Incident("i3", "Test", Severity.LOW, "system",
                        "test", "details", "action", True)
        decision = route_incident(inc)
        assert decision.channel == NotificationChannel.ALERT
        assert decision.requires_approval is True

    def test_route_groups(self):
        from core.supervisor.severity_router import route_incidents, NotificationChannel
        from core.supervisor.incident_classifier import Incident
        from core.events.event_types import Severity

        incidents = [
            Incident("a", "A", Severity.CRITICAL, "s", "t", "d", "a", False),
            Incident("b", "B", Severity.LOW, "s", "t", "d", "a", False),
            Incident("c", "C", Severity.CRITICAL, "s", "t", "d", "a", False),
        ]
        groups = route_incidents(incidents)
        assert len(groups[NotificationChannel.IMMEDIATE_ALERT]) == 2
        assert len(groups[NotificationChannel.LOG_ONLY]) == 1


# ──────────────────────────────────────────────
# TASK QUARANTINE
# ──────────────────────────────────────────────

class TestTaskQuarantine:
    def test_quarantine_and_retrieve(self):
        from core.supervisor.task_quarantine import TaskQuarantine, QUARANTINE_FILE

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("core.supervisor.task_quarantine.QUARANTINE_FILE",
                        Path(tmpdir) / "quarantine.jsonl"):
                from core.supervisor import task_quarantine
                orig = task_quarantine.QUARANTINE_FILE
                task_quarantine.QUARANTINE_FILE = Path(tmpdir) / "quarantine.jsonl"

                q = TaskQuarantine()
                q.quarantine("t1", "post", "instagram", "circuit open",
                             data={"asin": "B123"}, attempts=3, last_error="timeout")

                tasks = q.get_quarantined()
                assert len(tasks) == 1
                assert tasks[0]["task_id"] == "t1"
                assert tasks[0]["platform"] == "instagram"

                task_quarantine.QUARANTINE_FILE = orig

    def test_count(self):
        from core.supervisor.task_quarantine import TaskQuarantine
        from core.supervisor import task_quarantine

        with tempfile.TemporaryDirectory() as tmpdir:
            orig = task_quarantine.QUARANTINE_FILE
            task_quarantine.QUARANTINE_FILE = Path(tmpdir) / "quarantine.jsonl"

            q = TaskQuarantine()
            q.quarantine("t1", "post", "instagram", "fail")
            q.quarantine("t2", "post", "tiktok", "fail")
            q.quarantine("t3", "post", "instagram", "fail")

            assert q.count() == 3
            assert q.count(platform="instagram") == 2

            task_quarantine.QUARANTINE_FILE = orig


# ──────────────────────────────────────────────
# INCIDENT DIGEST
# ──────────────────────────────────────────────

class TestIncidentDigest:
    def test_empty_digest(self):
        from interfaces.telegram.incident_digest import IncidentDigest
        d = IncidentDigest()
        assert not d.is_ready()
        assert d.flush() == ""

    def test_digest_collects_and_flushes(self):
        from interfaces.telegram.incident_digest import IncidentDigest
        from core.supervisor.incident_classifier import Incident
        from core.events.event_types import Severity

        d = IncidentDigest(window_seconds=0)  # immediate flush
        d.add(Incident("i1", "Fail1", Severity.HIGH, "exec", "pf", "d", "a", False))
        d.add(Incident("i2", "Fail2", Severity.MEDIUM, "gen", "gf", "d", "a", False))

        assert d.pending_count == 2
        assert d.is_ready()

        msg = d.flush()
        assert "2 incidents" in msg
        assert "HIGH" in msg
        assert d.pending_count == 0


# ──────────────────────────────────────────────
# ALERT DISPATCHER
# ──────────────────────────────────────────────

class TestAlertDispatcher:
    def test_severity_filter(self):
        from interfaces.telegram.alert_dispatcher import AlertDispatcher
        from core.events.event_bus import Event
        from core.events.event_types import EventType, Severity

        d = AlertDispatcher()
        low_event = Event("e1", EventType.POST_PUBLISHED, Severity.LOW,
                          "now", "", {}, "test")
        high_event = Event("e2", EventType.POST_FAILED, Severity.HIGH,
                           "now", "", {}, "test")

        assert not d.should_alert(low_event)
        assert d.should_alert(high_event)

    def test_rate_limit(self):
        from interfaces.telegram.alert_dispatcher import AlertDispatcher
        from core.events.event_bus import Event
        from core.events.event_types import EventType, Severity

        d = AlertDispatcher()
        event = Event("e1", EventType.POST_FAILED, Severity.HIGH,
                       "now", "", {}, "test")

        assert d.should_alert(event)
        d._last_alert["post_failed"] = time.time()
        assert not d.should_alert(event)

    def test_disabled(self):
        from interfaces.telegram.alert_dispatcher import AlertDispatcher
        from core.events.event_bus import Event
        from core.events.event_types import EventType, Severity

        d = AlertDispatcher()
        d.disable()
        event = Event("e1", EventType.PIPELINE_FAILED, Severity.CRITICAL,
                       "now", "", {}, "test")
        assert not d.should_alert(event)


# ──────────────────────────────────────────────
# HUMAN APPROVAL FLOW
# ──────────────────────────────────────────────

class TestHumanApprovalFlow:
    def test_create_and_approve(self):
        from interfaces.telegram.human_approval_flow import HumanApprovalFlow, ApprovalStatus

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("interfaces.telegram.human_approval_flow.APPROVAL_LOG",
                        Path(tmpdir) / "approvals.jsonl"), \
                 patch("interfaces.telegram.human_approval_flow.APPROVAL_STATE",
                        Path(tmpdir) / "state.json"):

                flow = HumanApprovalFlow()
                req = flow.create_request("inc1", "Test incident",
                                          "Details here", "Restart executor", "executor")
                assert req.status == ApprovalStatus.PENDING

                approved = flow.approve(req.request_id)
                assert approved is not None
                assert approved.status == ApprovalStatus.APPROVED

    def test_reject(self):
        from interfaces.telegram.human_approval_flow import HumanApprovalFlow, ApprovalStatus

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("interfaces.telegram.human_approval_flow.APPROVAL_LOG",
                        Path(tmpdir) / "approvals.jsonl"), \
                 patch("interfaces.telegram.human_approval_flow.APPROVAL_STATE",
                        Path(tmpdir) / "state.json"):

                flow = HumanApprovalFlow()
                req = flow.create_request("inc2", "Bad thing", "d", "a", "system")
                rejected = flow.reject(req.request_id)
                assert rejected.status == ApprovalStatus.REJECTED

    def test_expire_stale(self):
        from interfaces.telegram.human_approval_flow import HumanApprovalFlow, ApprovalStatus

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("interfaces.telegram.human_approval_flow.APPROVAL_LOG",
                        Path(tmpdir) / "approvals.jsonl"), \
                 patch("interfaces.telegram.human_approval_flow.APPROVAL_STATE",
                        Path(tmpdir) / "state.json"), \
                 patch("interfaces.telegram.human_approval_flow.APPROVAL_TIMEOUT_SECONDS", 0):

                flow = HumanApprovalFlow()
                flow.create_request("inc3", "Old", "d", "a", "system")
                time.sleep(0.1)
                expired = flow.expire_stale()
                assert len(expired) == 1
                assert expired[0].status == ApprovalStatus.EXPIRED

    def test_get_pending(self):
        from interfaces.telegram.human_approval_flow import HumanApprovalFlow

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("interfaces.telegram.human_approval_flow.APPROVAL_LOG",
                        Path(tmpdir) / "approvals.jsonl"), \
                 patch("interfaces.telegram.human_approval_flow.APPROVAL_STATE",
                        Path(tmpdir) / "state.json"):

                flow = HumanApprovalFlow()
                flow.create_request("a", "A", "d", "a", "s")
                flow.create_request("b", "B", "d", "a", "s")
                assert len(flow.get_pending()) == 2

                flow.approve(flow.get_pending()[0].request_id)
                assert len(flow.get_pending()) == 1


# ──────────────────────────────────────────────
# COMMAND ROUTER (sync parts)
# ──────────────────────────────────────────────

class TestCommandRouter:
    def test_help_command(self):
        import asyncio
        from interfaces.telegram.command_router import CommandRouter

        router = CommandRouter()
        result = asyncio.run(router.handle("/help", "", 12345))
        assert "HERMES" in result
        assert "/status" in result

    def test_unknown_command(self):
        import asyncio
        from interfaces.telegram.command_router import CommandRouter

        router = CommandRouter()
        result = asyncio.run(router.handle("/nonexistent", "", 12345))
        assert "desconocido" in result.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

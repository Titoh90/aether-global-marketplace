"""
Tests for IMPERIO Hybrid Architecture — 4-Layer System.
Covers: correlation, pipeline_lock, log_rotator, circuit_breaker,
        ai_spend_governor, content_quality_gate.
"""

import gzip
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest


# ── Correlation Tests ────────────────────────────────────────────────────────

class TestCorrelation:
    def test_new_trace_returns_string(self):
        from core.observability.correlation import new_trace
        tid = new_trace()
        assert isinstance(tid, str)
        assert len(tid) == 16

    def test_get_current_trace_after_new(self):
        from core.observability.correlation import new_trace, get_current_trace
        tid = new_trace()
        assert get_current_trace() == tid

    def test_set_current_trace(self):
        from core.observability.correlation import set_current_trace, get_current_trace
        set_current_trace("abc123")
        assert get_current_trace() == "abc123"

    def test_trace_context_returns_dict(self):
        from core.observability.correlation import new_trace, trace_context
        new_trace()
        ctx = trace_context()
        assert "trace_id" in ctx
        assert "started_at" in ctx
        assert ctx["trace_id"] is not None

    def test_env_var_override(self):
        from core.observability.correlation import new_trace, get_current_trace
        with patch.dict(os.environ, {"IMPERIO_TRACE_ID": "envtrace12345678"}):
            tid = new_trace()
            assert tid == "envtrace12345678"
            assert get_current_trace() == "envtrace12345678"

    def test_thread_isolation(self):
        from core.observability.correlation import new_trace, get_current_trace
        results = {}

        def worker(name):
            tid = new_trace()
            time.sleep(0.01)
            results[name] = get_current_trace()

        t1 = threading.Thread(target=worker, args=("t1",))
        t2 = threading.Thread(target=worker, args=("t2",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Each thread should have its own trace_id
        assert results["t1"] != results["t2"]

    def test_get_current_trace_none_when_unset(self):
        from core.observability import correlation
        # Clear thread-local
        if hasattr(correlation._local, "trace_id"):
            del correlation._local.trace_id
        assert correlation.get_current_trace() is None


# ── Pipeline Lock Tests ──────────────────────────────────────────────────────

class TestPipelineLock:
    def test_lock_acquires_and_releases(self):
        from core.guardrails.pipeline_lock import pipeline_lock
        with pipeline_lock("test_lock", timeout_seconds=5):
            # Lock held — should work
            assert True

    def test_concurrent_lock_raises(self):
        from core.guardrails.pipeline_lock import pipeline_lock, PipelineAlreadyRunningError
        with pipeline_lock("test_concurrent", timeout_seconds=1):
            with pytest.raises(PipelineAlreadyRunningError):
                with pipeline_lock("test_concurrent", timeout_seconds=0):
                    pass

    def test_lock_writes_pid(self):
        from core.guardrails.pipeline_lock import pipeline_lock
        lock_path = Path("/tmp/imperio-pipeline-test_pid.lock")
        with pipeline_lock("test_pid", timeout_seconds=1):
            content = lock_path.read_text().strip()
            assert content == str(os.getpid())

    def test_different_names_independent(self):
        from core.guardrails.pipeline_lock import pipeline_lock
        with pipeline_lock("test_a", timeout_seconds=1):
            with pipeline_lock("test_b", timeout_seconds=1):
                assert True  # Both locks held simultaneously


# ── Log Rotator Tests ────────────────────────────────────────────────────────

class TestLogRotator:
    def test_compress_old_file(self):
        from core.observability.log_rotator import rotate_logs
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create old JSONL file
            old_file = Path(tmpdir) / "old_log.jsonl"
            old_file.write_text('{"event": "test"}\n' * 100)
            # Set mtime to 10 days ago
            old_time = time.time() - (10 * 86400)
            os.utime(old_file, (old_time, old_time))

            report = rotate_logs([Path(tmpdir)], compress_after_days=7)
            assert len(report.compressed) == 1
            assert not old_file.exists()
            assert Path(str(old_file) + ".gz").exists()

    def test_skip_recent_file(self):
        from core.observability.log_rotator import rotate_logs
        with tempfile.TemporaryDirectory() as tmpdir:
            recent = Path(tmpdir) / "recent.jsonl"
            recent.write_text('{"event": "test"}\n' * 100)

            report = rotate_logs([Path(tmpdir)], compress_after_days=7)
            assert len(report.compressed) == 0
            assert recent.exists()

    def test_delete_ancient_gz(self):
        from core.observability.log_rotator import rotate_logs
        with tempfile.TemporaryDirectory() as tmpdir:
            ancient = Path(tmpdir) / "ancient.jsonl.gz"
            ancient.write_bytes(b"compressed data")
            old_time = time.time() - (100 * 86400)
            os.utime(ancient, (old_time, old_time))

            report = rotate_logs([Path(tmpdir)], delete_after_days=90)
            assert len(report.deleted) == 1
            assert not ancient.exists()

    def test_skip_small_files(self):
        from core.observability.log_rotator import rotate_logs
        with tempfile.TemporaryDirectory() as tmpdir:
            small = Path(tmpdir) / "tiny.jsonl"
            small.write_text("{}\n")
            old_time = time.time() - (10 * 86400)
            os.utime(small, (old_time, old_time))

            report = rotate_logs([Path(tmpdir)], compress_after_days=7)
            assert len(report.compressed) == 0

    def test_report_str(self):
        from core.observability.log_rotator import RotationReport
        r = RotationReport(compressed=["a"], deleted=["b"], skipped=3)
        assert "1 compressed" in str(r)
        assert "1 deleted" in str(r)

    def test_nonexistent_dir_skipped(self):
        from core.observability.log_rotator import rotate_logs
        report = rotate_logs([Path("/nonexistent/dir")])
        assert len(report.compressed) == 0
        assert len(report.errors) == 0


# ── Circuit Breaker Tests ────────────────────────────────────────────────────

class TestCircuitBreaker:
    def _make_cb(self, tmpdir, **kwargs):
        from core.guardrails.circuit_breaker import CircuitBreaker
        state_file = Path(tmpdir) / "cb_state.json"
        return CircuitBreaker(state_file=state_file, **kwargs)

    def test_initial_state_closed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = self._make_cb(tmpdir)
            assert not cb.is_open("instagram")

    def test_success_keeps_closed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = self._make_cb(tmpdir)
            cb.record_success("instagram")
            assert not cb.is_open("instagram")

    def test_failures_open_circuit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = self._make_cb(tmpdir, failure_threshold=3)
            cb.record_failure("instagram", "timeout")
            cb.record_failure("instagram", "timeout")
            assert not cb.is_open("instagram")  # 2 < 3
            cb.record_failure("instagram", "timeout")
            assert cb.is_open("instagram")  # 3 >= 3 → OPEN

    def test_success_resets_counter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = self._make_cb(tmpdir, failure_threshold=3)
            cb.record_failure("tiktok", "error")
            cb.record_failure("tiktok", "error")
            cb.record_success("tiktok")
            cb.record_failure("tiktok", "error")
            assert not cb.is_open("tiktok")  # counter reset

    def test_cooldown_transitions_to_half_open(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = self._make_cb(tmpdir, failure_threshold=2, cooldown_seconds=1)
            cb.record_failure("twitter", "error")
            cb.record_failure("twitter", "error")
            assert cb.is_open("twitter")
            time.sleep(1.1)
            assert not cb.is_open("twitter")  # HALF_OPEN → allow test

    def test_half_open_success_closes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = self._make_cb(tmpdir, failure_threshold=2, cooldown_seconds=0)
            cb.record_failure("pinterest", "error")
            cb.record_failure("pinterest", "error")
            # Cooldown = 0, so immediate HALF_OPEN
            time.sleep(0.05)
            cb.record_success("pinterest")
            status = cb.get_status()
            assert status["pinterest"]["state"] == "CLOSED"

    def test_get_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = self._make_cb(tmpdir)
            cb.record_failure("facebook", "error")
            cb.record_success("instagram")
            status = cb.get_status()
            assert "facebook" in status
            assert "instagram" in status
            assert status["facebook"]["consecutive_failures"] == 1
            assert status["instagram"]["total_successes"] == 1

    def test_state_persists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from core.guardrails.circuit_breaker import CircuitBreaker
            state_file = Path(tmpdir) / "cb_state.json"

            cb1 = CircuitBreaker(state_file=state_file, failure_threshold=2)
            cb1.record_failure("youtube", "error")
            cb1.record_failure("youtube", "error")

            # Load from same file
            cb2 = CircuitBreaker(state_file=state_file, failure_threshold=2)
            assert cb2.is_open("youtube")

    def test_reset(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = self._make_cb(tmpdir, failure_threshold=2)
            cb.record_failure("twitter", "error")
            cb.record_failure("twitter", "error")
            assert cb.is_open("twitter")
            cb.reset("twitter")
            assert not cb.is_open("twitter")

    def test_independent_executors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cb = self._make_cb(tmpdir, failure_threshold=2)
            cb.record_failure("instagram", "error")
            cb.record_failure("instagram", "error")
            assert cb.is_open("instagram")
            assert not cb.is_open("tiktok")


# ── AI Spend Governor Tests ─────────────────────────────────────────────────

class TestAISpendGovernor:
    def test_proceed_no_budget(self):
        from core.guardrails.ai_spend_governor import check_budget, SpendDecision
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("IMPERIO_DAILY_AI_BUDGET_USD", None)
            result = check_budget("openrouter", 1000)
            assert result == SpendDecision.PROCEED

    def test_block_over_budget(self):
        from core.guardrails.ai_spend_governor import (
            check_budget, record_spend, SpendDecision, _spend_file, _today
        )
        with patch.dict(os.environ, {"IMPERIO_DAILY_AI_BUDGET_USD": "0.001"}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch("core.guardrails.ai_spend_governor.SPEND_DIR",
                          Path(tmpdir)):
                    record_spend("anthropic", tokens_used=10000, cost_usd=0.002)
                    result = check_budget("anthropic", 1000)
                    assert result == SpendDecision.BLOCK

    def test_downgrade_near_budget(self):
        from core.guardrails.ai_spend_governor import (
            check_budget, record_spend, SpendDecision
        )
        with patch.dict(os.environ, {"IMPERIO_DAILY_AI_BUDGET_USD": "0.01"}):
            with tempfile.TemporaryDirectory() as tmpdir:
                with patch("core.guardrails.ai_spend_governor.SPEND_DIR",
                          Path(tmpdir)):
                    record_spend("openrouter", tokens_used=5000, cost_usd=0.0085)
                    result = check_budget("openrouter", 100)
                    assert result == SpendDecision.DOWNGRADE_TIER

    def test_record_spend_accumulates(self):
        from core.guardrails.ai_spend_governor import record_spend, get_daily_spend
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("core.guardrails.ai_spend_governor.SPEND_DIR",
                      Path(tmpdir)):
                record_spend("groq", tokens_used=100, cost_usd=0.001)
                record_spend("groq", tokens_used=200, cost_usd=0.002)
                spend = get_daily_spend()
                assert spend["total_calls"] == 2
                assert spend["total_tokens"] == 300

    def test_get_daily_spend_format(self):
        from core.guardrails.ai_spend_governor import get_daily_spend
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("core.guardrails.ai_spend_governor.SPEND_DIR",
                      Path(tmpdir)):
                spend = get_daily_spend()
                assert "date" in spend
                assert "providers" in spend
                assert "total_cost_usd" in spend
                assert "budget_remaining" in spend


# ── Content Quality Gate Tests ───────────────────────────────────────────────

class TestContentQualityGate:
    def test_good_content_passes(self):
        from core.quality.content_quality_gate import evaluate
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("core.quality.content_quality_gate.QUALITY_LOG",
                      Path(tmpdir) / "qg.jsonl"):
                result = evaluate({
                    "caption": (
                        "The frustration is real. You know the feeling.\n\n"
                        "Owala FreeSip exists because of that exact problem.\n\n"
                        "4.7 stars from 122,151 people who know.\n\n"
                        "Your future self will thank you."
                    ),
                    "product_name": "Owala FreeSip",
                    "asin": "B0BZYCJK89",
                    "platform": "instagram",
                    "affiliate_url": "https://amzn.to/abc123",
                })
                assert result.score >= 60
                assert result.passed

    def test_empty_caption_low_score(self):
        from core.quality.content_quality_gate import evaluate
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("core.quality.content_quality_gate.QUALITY_LOG",
                      Path(tmpdir) / "qg.jsonl"):
                result = evaluate({"caption": "", "platform": "instagram"})
                assert result.score <= 50  # empty caption still gets partial credit from other checks
                assert any("empty caption" in r for r in result.reasons)

    def test_placeholder_detected(self):
        from core.quality.content_quality_gate import evaluate
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("core.quality.content_quality_gate.QUALITY_LOG",
                      Path(tmpdir) / "qg.jsonl"):
                result = evaluate({
                    "caption": "Check out [product] — it's amazing! TODO add link",
                    "platform": "instagram",
                })
                assert any("no_placeholders" in r and "FAIL" in r
                          for r in result.reasons)

    def test_twitter_over_limit(self):
        from core.quality.content_quality_gate import evaluate
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("core.quality.content_quality_gate.QUALITY_LOG",
                      Path(tmpdir) / "qg.jsonl"):
                result = evaluate({
                    "caption": "x" * 300,
                    "platform": "twitter",
                })
                assert any("EXCEEDS" in r for r in result.reasons)

    def test_shadow_mode_default(self):
        from core.quality.content_quality_gate import evaluate
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("core.quality.content_quality_gate.QUALITY_LOG",
                      Path(tmpdir) / "qg.jsonl"):
                result = evaluate({"caption": "test", "platform": "instagram"})
                assert result.mode == "shadow"

    def test_result_is_frozen(self):
        from core.quality.content_quality_gate import evaluate
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("core.quality.content_quality_gate.QUALITY_LOG",
                      Path(tmpdir) / "qg.jsonl"):
                result = evaluate({
                    "caption": "Good content here.",
                    "platform": "instagram",
                })
                with pytest.raises(AttributeError):
                    result.score = 100

    def test_logs_to_jsonl(self):
        from core.quality.content_quality_gate import evaluate
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "qg.jsonl"
            with patch("core.quality.content_quality_gate.QUALITY_LOG",
                      log_path):
                evaluate({
                    "caption": "Test content for logging.",
                    "platform": "instagram",
                    "product_name": "TestProduct",
                })
                assert log_path.exists()
                entry = json.loads(log_path.read_text().strip())
                assert "score" in entry
                assert entry["platform"] == "instagram"

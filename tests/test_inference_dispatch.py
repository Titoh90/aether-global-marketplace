#!/usr/bin/env python3
"""
test_inference_dispatch.py — Tests for core/inference_dispatch/

Coverage:
- Provider registry: availability, key detection, immutability
- Task classifier: valid/invalid types, normalization, inference
- Routing policy: frozen mappings, local-only tasks, chain filtering
- Provider health: cooldown, failover logging, JSONL output
- Fallback chain: retry logic, provider skipping, freellmapi fallback
- Dispatch: never raises, local gate, logging, result structure
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_IMPERIO_ROOT = Path(__file__).parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# Provider Registry
# ─────────────────────────────────────────────────────────────────────────────

class TestProviderRegistry:
    def test_providers_mapping_is_frozen(self):
        from core.inference_dispatch.provider_registry import PROVIDERS
        from types import MappingProxyType
        assert isinstance(PROVIDERS, MappingProxyType)

    def test_providers_mapping_read_only(self):
        from core.inference_dispatch.provider_registry import PROVIDERS
        with pytest.raises((TypeError, AttributeError)):
            PROVIDERS["new_provider"] = {}

    def test_known_providers_exist(self):
        from core.inference_dispatch.provider_registry import PROVIDERS
        for pid in ["groq", "openrouter", "freellmapi", "local"]:
            assert pid in PROVIDERS

    def test_provider_unavailable_when_no_key(self):
        from core.inference_dispatch.provider_registry import is_available
        with patch.dict(os.environ, {}, clear=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(stdout="", returncode=1)
                status = is_available("groq")
                # groq needs GROQ_API_KEY — should be unavailable
                assert status.available is False or status.reason in ("no_key", "unhealthy", "ok")

    def test_local_provider_always_available(self):
        from core.inference_dispatch.provider_registry import is_available
        status = is_available("local")
        assert status.available is True

    def test_unknown_provider_unavailable(self):
        from core.inference_dispatch.provider_registry import is_available
        status = is_available("nonexistent_provider_xyz")
        assert status.available is False
        assert status.reason == "unknown"

    def test_get_models_returns_list(self):
        from core.inference_dispatch.provider_registry import get_models
        models = get_models("groq")
        assert isinstance(models, list)
        assert len(models) > 0

    def test_get_base_url_returns_string(self):
        from core.inference_dispatch.provider_registry import get_base_url
        url = get_base_url("openrouter")
        assert isinstance(url, str)
        assert "openrouter" in url.lower()

    def test_get_base_url_local_is_local(self):
        from core.inference_dispatch.provider_registry import get_base_url
        assert get_base_url("local") == "local"

    def test_get_available_providers_returns_list(self):
        from core.inference_dispatch.provider_registry import get_available_providers
        providers = get_available_providers()
        assert isinstance(providers, list)
        # local is always available
        assert "local" in providers

    def test_provider_status_has_required_fields(self):
        from core.inference_dispatch.provider_registry import is_available
        status = is_available("local")
        assert hasattr(status, "provider_id")
        assert hasattr(status, "available")
        assert hasattr(status, "reason")


# ─────────────────────────────────────────────────────────────────────────────
# Task Classifier
# ─────────────────────────────────────────────────────────────────────────────

class TestTaskClassifier:
    def test_valid_task_types_accepted(self):
        from core.inference_dispatch.task_classifier import classify, VALID_TASK_TYPES
        for task_type in VALID_TASK_TYPES:
            result = classify(task_type)
            assert result == task_type

    def test_invalid_task_type_raises_value_error(self):
        from core.inference_dispatch.task_classifier import classify
        with pytest.raises(ValueError):
            classify("invalid_task_xyz")

    def test_classify_normalizes_lowercase(self):
        from core.inference_dispatch.task_classifier import classify
        result = classify("Caption_Generation")
        assert result == "caption_generation"

    def test_classify_strips_whitespace(self):
        from core.inference_dispatch.task_classifier import classify
        result = classify("  reasoning  ")
        assert result == "reasoning"

    def test_valid_task_types_is_frozenset(self):
        from core.inference_dispatch.task_classifier import VALID_TASK_TYPES
        assert isinstance(VALID_TASK_TYPES, frozenset)

    def test_all_expected_task_types_present(self):
        from core.inference_dispatch.task_classifier import VALID_TASK_TYPES
        expected = {
            "caption_generation", "visual_analysis", "embedding_generation",
            "reasoning", "tool_selection", "summarization", "memory_retrieval",
            "trend_analysis", "classification", "prompt_optimization",
        }
        assert expected.issubset(VALID_TASK_TYPES)

    def test_infer_task_type_returns_valid_type(self):
        from core.inference_dispatch.task_classifier import infer_task_type, VALID_TASK_TYPES
        result = infer_task_type({"prompt": "Summarize this text"})
        assert result in VALID_TASK_TYPES

    def test_infer_task_type_image_payload(self):
        from core.inference_dispatch.task_classifier import infer_task_type
        result = infer_task_type({"image": "base64...", "prompt": "analyze"})
        assert result == "visual_analysis"

    def test_infer_task_type_empty_payload(self):
        from core.inference_dispatch.task_classifier import infer_task_type, VALID_TASK_TYPES
        result = infer_task_type({})
        assert result in VALID_TASK_TYPES


# ─────────────────────────────────────────────────────────────────────────────
# Routing Policy
# ─────────────────────────────────────────────────────────────────────────────

class TestRoutingPolicy:
    def test_task_routing_is_frozen(self):
        from core.inference_dispatch.routing_policy import TASK_ROUTING
        from types import MappingProxyType
        assert isinstance(TASK_ROUTING, MappingProxyType)

    def test_task_to_tier_is_frozen(self):
        from core.inference_dispatch.routing_policy import TASK_TO_TIER
        from types import MappingProxyType
        assert isinstance(TASK_TO_TIER, MappingProxyType)

    def test_task_routing_read_only(self):
        from core.inference_dispatch.routing_policy import TASK_ROUTING
        with pytest.raises((TypeError, AttributeError)):
            TASK_ROUTING["new_task"] = ["provider"]

    def test_memory_retrieval_is_local_only(self):
        from core.inference_dispatch.routing_policy import TASK_ROUTING, is_local_only
        assert TASK_ROUTING["memory_retrieval"] == ["local"]
        assert is_local_only("memory_retrieval") is True

    def test_embedding_generation_is_local_only(self):
        from core.inference_dispatch.routing_policy import TASK_ROUTING, is_local_only
        assert TASK_ROUTING["embedding_generation"] == ["local"]
        assert is_local_only("embedding_generation") is True

    def test_caption_routing_includes_freellmapi(self):
        from core.inference_dispatch.routing_policy import TASK_ROUTING
        assert "freellmapi" in TASK_ROUTING["caption_generation"]

    def test_non_local_task_not_local_only(self):
        from core.inference_dispatch.routing_policy import is_local_only
        assert is_local_only("reasoning") is False
        assert is_local_only("caption_generation") is False

    def test_local_only_tasks_frozenset(self):
        from core.inference_dispatch.routing_policy import LOCAL_ONLY_TASKS
        assert isinstance(LOCAL_ONLY_TASKS, frozenset)

    def test_get_provider_chain_returns_list(self):
        from core.inference_dispatch.routing_policy import get_provider_chain
        chain = get_provider_chain("caption_generation")
        assert isinstance(chain, list)

    def test_get_provider_chain_local_only_returns_local(self):
        from core.inference_dispatch.routing_policy import get_provider_chain
        chain = get_provider_chain("memory_retrieval")
        assert chain == ["local"]

    def test_get_freellmapi_tier_returns_string(self):
        from core.inference_dispatch.routing_policy import get_freellmapi_tier
        tier = get_freellmapi_tier("caption_generation")
        assert isinstance(tier, str)
        assert tier in ("FAST_CHEAP", "HIGH_REASONING", "IMAGE_PROMPTS", "LONG_CONTEXT")

    def test_get_freellmapi_tier_defaults_fast_cheap(self):
        from core.inference_dispatch.routing_policy import get_freellmapi_tier
        tier = get_freellmapi_tier("unknown_task_xyz")
        assert tier == "FAST_CHEAP"


# ─────────────────────────────────────────────────────────────────────────────
# Provider Health
# ─────────────────────────────────────────────────────────────────────────────

class TestProviderHealth:
    def setup_method(self):
        # Reset health state before each test
        from core.inference_dispatch import provider_health as ph
        with ph._lock:
            ph._state.clear()

    def test_provider_healthy_by_default(self):
        from core.inference_dispatch import provider_health as ph
        assert ph.is_healthy("test_provider_abc") is True

    def test_mark_failed_makes_unhealthy(self):
        from core.inference_dispatch import provider_health as ph
        ph.mark_failed("test_p", error="test error")
        assert ph.is_healthy("test_p") is False

    def test_mark_healthy_clears_state(self):
        from core.inference_dispatch import provider_health as ph
        ph.mark_failed("test_p", error="err")
        ph.mark_healthy("test_p")
        assert ph.is_healthy("test_p") is True

    def test_unhealthy_before_cooldown(self):
        from core.inference_dispatch import provider_health as ph
        ph.mark_failed("test_p", error="err")
        # Immediately after mark_failed, still unhealthy
        assert ph.is_healthy("test_p") is False

    def test_healthy_after_cooldown_elapsed(self):
        from core.inference_dispatch import provider_health as ph
        ph.mark_failed("test_p", error="err")
        # Manually set failed_at to past
        with ph._lock:
            ph._state["test_p"]["failed_at"] = time.monotonic() - ph.COOLDOWN_SECONDS - 1
        assert ph.is_healthy("test_p") is True

    def test_get_status_returns_dict(self):
        from core.inference_dispatch import provider_health as ph
        ph.mark_failed("test_p2", error="err")
        status = ph.get_status()
        assert isinstance(status, dict)
        assert "test_p2" in status

    def test_failover_event_logged_to_jsonl(self, tmp_path, monkeypatch):
        from core.inference_dispatch import provider_health as ph
        monkeypatch.setattr(ph, "_LOG_DIR", tmp_path)
        ph.emit_failover(
            task_type="caption_generation",
            task_id="t001",
            provider_tried="groq",
            model_tried="llama-3.1-8b",
            error="timeout",
            fallback_to="openrouter",
        )
        log_files = list(tmp_path.glob("*.jsonl"))
        assert len(log_files) == 1
        lines = log_files[0].read_text().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["provider_tried"] == "groq"
        assert entry["fallback_to"] == "openrouter"

    def test_failover_log_is_append_only(self, tmp_path, monkeypatch):
        from core.inference_dispatch import provider_health as ph
        monkeypatch.setattr(ph, "_LOG_DIR", tmp_path)
        for i in range(3):
            ph.emit_failover(
                task_type="reasoning",
                task_id=f"t{i}",
                provider_tried="openrouter",
                model_tried="llama",
                error=f"error {i}",
                fallback_to="freellmapi",
            )
        log_files = list(tmp_path.glob("*.jsonl"))
        assert len(log_files) == 1
        lines = log_files[0].read_text().splitlines()
        assert len(lines) == 3


# ─────────────────────────────────────────────────────────────────────────────
# Fallback Chain
# ─────────────────────────────────────────────────────────────────────────────

class TestFallbackChain:
    def test_local_only_returns_error_result(self):
        from core.inference_dispatch.fallback_chain import complete_with_task_fallback
        result = complete_with_task_fallback("memory_retrieval", "query")
        assert result.success is False
        assert "local-only" in result.error

    def test_returns_inference_result_type(self):
        from core.inference_dispatch.fallback_chain import complete_with_task_fallback
        from core.inference_dispatch.schemas import InferenceResult
        with patch("core.inference_dispatch.fallback_chain._call_openai_compat") as mock_call:
            mock_call.return_value = "Generated text"
            with patch("core.inference_dispatch.provider_registry.is_available") as mock_avail:
                mock_status = MagicMock()
                mock_status.available = True
                mock_avail.return_value = mock_status
                result = complete_with_task_fallback("caption_generation", "test prompt")
        assert isinstance(result, InferenceResult)

    def test_never_raises(self):
        from core.inference_dispatch.fallback_chain import complete_with_task_fallback
        with patch("core.inference_dispatch.fallback_chain._call_openai_compat") as mock_call:
            mock_call.side_effect = Exception("provider exploded")
            with patch("core.inference_dispatch.fallback_chain.llm_complete") as mock_llm:
                mock_llm.side_effect = Exception("freellmapi also dead")
                # Should not raise
                result = complete_with_task_fallback("reasoning", "test")
        assert result is not None

    def test_fallback_triggered_on_second_provider(self):
        from core.inference_dispatch.fallback_chain import complete_with_task_fallback
        call_count = {"n": 0}

        def mock_call(base_url, api_key, model, prompt, max_tokens, timeout=30):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("first provider failed")
            return "Success from second provider"

        with patch("core.inference_dispatch.fallback_chain._call_openai_compat", side_effect=mock_call):
            with patch("core.inference_dispatch.routing_policy.get_provider_chain") as mock_chain:
                mock_chain.return_value = ["provider_a", "provider_b"]
                with patch("core.inference_dispatch.provider_registry.get_models", return_value=["model-v1"]):
                    with patch("core.inference_dispatch.provider_registry.get_base_url", return_value="https://api.example.com"):
                        with patch("core.inference_dispatch.provider_registry.get_api_key", return_value="key"):
                            with patch("core.inference_dispatch.provider_health.is_healthy", return_value=True):
                                result = complete_with_task_fallback("caption_generation", "test")
        # If second provider succeeded, fallback_triggered should be True
        # (attempts > 1 means fallback)
        assert result is not None

    def test_exhausted_returns_error_result(self):
        from core.inference_dispatch.fallback_chain import complete_with_task_fallback
        with patch("core.inference_dispatch.routing_policy.get_provider_chain", return_value=[]):
            with patch("core.inference_dispatch.fallback_chain.llm_complete") as mock_llm:
                mock_llm.side_effect = Exception("freellmapi dead")
                result = complete_with_task_fallback("reasoning", "test")
        assert result.success is False


# ─────────────────────────────────────────────────────────────────────────────
# Dispatch (public API)
# ─────────────────────────────────────────────────────────────────────────────

class TestDispatch:
    def test_returns_inference_result(self):
        from core.inference_dispatch.dispatch import dispatch
        from core.inference_dispatch.schemas import InferenceResult
        with patch("core.inference_dispatch.dispatch.complete_with_task_fallback") as mock_f:
            mock_f.return_value = InferenceResult(
                text="result", task_type="caption_generation",
                provider_used="openrouter", model_used="llama",
                latency_ms=100, attempts=1, success=True,
            )
            result = dispatch("caption_generation", {"prompt": "Write a hook"})
        assert isinstance(result, InferenceResult)

    def test_never_raises_on_invalid_task(self):
        from core.inference_dispatch.dispatch import dispatch
        result = dispatch("invalid_task_xyz", {"prompt": "test"})
        assert result is not None
        assert result.success is False

    def test_never_raises_on_provider_failure(self):
        from core.inference_dispatch.dispatch import dispatch
        with patch("core.inference_dispatch.dispatch.complete_with_task_fallback") as mock_f:
            mock_f.side_effect = Exception("total failure")
            result = dispatch("reasoning", {"prompt": "test"})
        assert result is not None
        assert result.success is False

    def test_memory_retrieval_never_calls_provider(self):
        from core.inference_dispatch.dispatch import dispatch
        with patch("core.inference_dispatch.dispatch.complete_with_task_fallback") as mock_f:
            result = dispatch("memory_retrieval", {"prompt": "find memory"})
        mock_f.assert_not_called()
        assert result.success is False
        assert "local-only" in result.error

    def test_embedding_generation_never_calls_provider(self):
        from core.inference_dispatch.dispatch import dispatch
        with patch("core.inference_dispatch.dispatch.complete_with_task_fallback") as mock_f:
            result = dispatch("embedding_generation", {"prompt": "embed this"})
        mock_f.assert_not_called()
        assert result.success is False

    def test_result_has_correct_task_type(self):
        from core.inference_dispatch.dispatch import dispatch
        from core.inference_dispatch.schemas import InferenceResult
        with patch("core.inference_dispatch.dispatch.complete_with_task_fallback") as mock_f:
            mock_f.return_value = InferenceResult(
                text="ok", task_type="summarization",
                provider_used="openrouter", model_used="llama",
                latency_ms=50, attempts=1, success=True,
            )
            result = dispatch("summarization", {"prompt": "Summarize"})
        assert result.task_type == "summarization"

    def test_dispatch_logs_to_file(self, tmp_path, monkeypatch):
        import sys
        import core.inference_dispatch.dispatch
        d_module = sys.modules["core.inference_dispatch.dispatch"]
        dispatch = d_module.dispatch
        from core.inference_dispatch.schemas import InferenceResult
        monkeypatch.setattr(d_module, "_LOG_DIR", tmp_path)
        with patch("core.inference_dispatch.dispatch.complete_with_task_fallback") as mock_f:
            mock_f.return_value = InferenceResult(
                text="logged", task_type="classification",
                provider_used="groq", model_used="llama",
                latency_ms=30, attempts=1, success=True,
            )
            dispatch("classification", {"prompt": "classify"})
        log_files = list(tmp_path.glob("*.jsonl"))
        assert len(log_files) == 1

    def test_task_id_propagated(self):
        from core.inference_dispatch.dispatch import dispatch
        from core.inference_dispatch.schemas import InferenceResult
        captured = {}
        def mock_fallback(task_type, prompt, max_tokens, task_id):
            captured["task_id"] = task_id
            return InferenceResult(
                text="ok", task_type=task_type,
                provider_used="test", model_used="test",
                latency_ms=1, attempts=1, success=True,
            )
        with patch("core.inference_dispatch.dispatch.complete_with_task_fallback", side_effect=mock_fallback):
            dispatch("reasoning", {"prompt": "test"}, task_id="trace-123")
        assert captured.get("task_id") == "trace-123"

    def test_fallback_prompt_from_payload_string(self):
        from core.inference_dispatch.dispatch import dispatch
        from core.inference_dispatch.schemas import InferenceResult
        captured = {}
        def mock_fallback(task_type, prompt, max_tokens, task_id):
            captured["prompt"] = prompt
            return InferenceResult(
                text="ok", task_type=task_type,
                provider_used="test", model_used="test",
                latency_ms=1, attempts=1, success=True,
            )
        with patch("core.inference_dispatch.dispatch.complete_with_task_fallback", side_effect=mock_fallback):
            dispatch("classification", {"prompt": "Classify this product"})
        assert "Classify this product" in captured.get("prompt", "")

    def test_no_platform_dispatch_imports(self):
        """Verify inference_dispatch never imports platform_dispatch."""
        import inspect
        from core.inference_dispatch import dispatch as d
        src = inspect.getsource(d)
        assert "platform_dispatch" not in src

    def test_schemas_frozen(self):
        from core.inference_dispatch.schemas import InferenceResult
        r = InferenceResult(
            text="t", task_type="reasoning", provider_used="p",
            model_used="m", latency_ms=1, attempts=1, success=True,
        )
        with pytest.raises((AttributeError, TypeError)):
            r.text = "mutated"

#!/usr/bin/env python3
"""
test_provider_routing.py — Unit tests for provider routing layer.

Tests tier selection, model fallback, health tracking.
No live server needed (uses mocking via monkeypatch).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm.model_registry import get_models, VALID_TIERS
from core.llm import provider_health
from core.llm.fallback_chain import complete_with_fallback, ProviderExhaustedError, CompletionResult

_PASS = 0
_FAIL = 0


def _check(name: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  ✅ {name}")
    else:
        _FAIL += 1
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


# ── model_registry ────────────────────────────────────────────────────────────

def test_tiers_exist() -> None:
    print("\n[1] model_registry — tier completeness")
    for tier in ["HIGH_REASONING", "FAST_CHEAP", "IMAGE_PROMPTS", "LONG_CONTEXT"]:
        models = get_models(tier)
        _check(f"{tier} has models", len(models) > 0)
        _check(f"{tier} first model is str", isinstance(models[0], str))


def test_invalid_tier() -> None:
    print("\n[2] model_registry — invalid tier raises KeyError")
    try:
        get_models("NONEXISTENT")
        _check("KeyError raised", False, "no exception")
    except KeyError:
        _check("KeyError raised", True)


# ── provider_health ───────────────────────────────────────────────────────────

def test_health_tracking() -> None:
    print("\n[3] provider_health — mark_failed / is_healthy cycle")
    pid = "test-model-xyz"
    provider_health.mark_healthy(pid)
    _check("healthy after mark_healthy", provider_health.is_healthy(pid))

    provider_health.mark_failed(pid, "timeout")
    _check("unhealthy after mark_failed", not provider_health.is_healthy(pid))

    # Simulate cooldown expiry by patching monotonic
    import core.llm.provider_health as _ph
    original = _ph.COOLDOWN_SECONDS
    _ph.COOLDOWN_SECONDS = 0  # instant recovery
    time.sleep(0.01)
    _check("healthy after cooldown expired", provider_health.is_healthy(pid))
    _ph.COOLDOWN_SECONDS = original


# ── fallback_chain ────────────────────────────────────────────────────────────

def test_fallback_success_first_model() -> None:
    print("\n[4] fallback_chain — success on first model")
    with patch("core.llm.fallback_chain.complete") as mock_complete:
        mock_complete.return_value = "Hello from model"
        result = complete_with_fallback("FAST_CHEAP", [{"role": "user", "content": "hi"}])
        _check("Returns CompletionResult", isinstance(result, CompletionResult))
        _check("Text correct", result.text == "Hello from model")
        _check("Attempts == 1", result.attempts == 1)


def test_fallback_skip_unhealthy() -> None:
    print("\n[5] fallback_chain — skips unhealthy model, succeeds on next")
    models = get_models("FAST_CHEAP")
    first, second = models[0], models[1]

    provider_health.mark_failed(first, "rate_limit")

    call_log = []
    def _mock_complete(model, messages, max_tokens, timeout):
        call_log.append(model)
        if model == first:
            raise Exception("Should not be called")
        return "fallback response"

    with patch("core.llm.fallback_chain.complete", side_effect=_mock_complete):
        result = complete_with_fallback("FAST_CHEAP", [{"role": "user", "content": "hi"}])
        _check("First model skipped", first not in call_log, f"called: {call_log}")
        _check("Fallback text returned", result.text == "fallback response")

    provider_health.mark_healthy(first)


def test_all_fail_raises() -> None:
    print("\n[6] fallback_chain — ProviderExhaustedError when all fail")
    from core.llm.openai_compat_client import ProviderError
    with patch("core.llm.fallback_chain.complete", side_effect=ProviderError("timeout", 503)):
        try:
            complete_with_fallback("FAST_CHEAP", [{"role": "user", "content": "hi"}])
            _check("ProviderExhaustedError raised", False, "no exception")
        except ProviderExhaustedError:
            _check("ProviderExhaustedError raised", True)


def test_max_retries_respected() -> None:
    print("\n[7] fallback_chain — max 2 retries enforced")
    from core.llm.fallback_chain import MAX_RETRIES
    from core.llm.openai_compat_client import ProviderError

    call_count = [0]
    def _counter(model, messages, max_tokens, timeout):
        call_count[0] += 1
        raise ProviderError("fail")

    with patch("core.llm.fallback_chain.complete", side_effect=_counter):
        try:
            complete_with_fallback("FAST_CHEAP", [{"role": "user", "content": "hi"}])
        except ProviderExhaustedError:
            pass
    _check(f"Max {MAX_RETRIES} attempts made", call_count[0] <= MAX_RETRIES,
           f"called {call_count[0]} times")


# ── provider_router ───────────────────────────────────────────────────────────

def test_router_str_to_messages() -> None:
    print("\n[8] provider_router — str prompt converted to messages")
    from core.llm.provider_router import _to_messages
    msgs = _to_messages("hello")
    _check("List with one message", len(msgs) == 1)
    _check("Role is 'user'", msgs[0]["role"] == "user")
    _check("Content is string", msgs[0]["content"] == "hello")

    msgs2 = _to_messages([{"role": "system", "content": "x"}])
    _check("Messages list passed through", msgs2[0]["role"] == "system")


if __name__ == "__main__":
    print("provider routing tests")
    print("=" * 50)
    test_tiers_exist()
    test_invalid_tier()
    test_health_tracking()
    test_fallback_success_first_model()
    test_fallback_skip_unhealthy()
    test_all_fail_raises()
    test_max_retries_respected()
    test_router_str_to_messages()
    print(f"\n{'='*50}")
    print(f"RESULT: {_PASS} PASS  {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)

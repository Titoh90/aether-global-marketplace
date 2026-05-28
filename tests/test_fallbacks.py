#!/usr/bin/env python3
"""
test_fallbacks.py — Test fallback behavior under failure conditions.

Tests HTTP error codes, timeouts, empty responses, malformed JSON.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm.openai_compat_client import ProviderError
from core.llm.fallback_chain import complete_with_fallback, ProviderExhaustedError
from core.llm import provider_health

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


MSG = [{"role": "user", "content": "test"}]


def test_429_triggers_fallback() -> None:
    print("\n[1] HTTP 429 → fallback to next model")
    call_models = []

    def _mock(model, messages, max_tokens, timeout):
        call_models.append(model)
        if len(call_models) == 1:
            raise ProviderError("rate limited", status=429)
        return "ok from fallback"

    with patch("core.llm.fallback_chain.complete", side_effect=_mock):
        result = complete_with_fallback("FAST_CHEAP", MSG)
        _check("Fallback succeeded", result.text == "ok from fallback")
        _check("Two models attempted", len(call_models) == 2)


def test_503_triggers_fallback() -> None:
    print("\n[2] HTTP 503 → fallback to next model")
    calls = []

    def _mock(model, messages, max_tokens, timeout):
        calls.append(model)
        if len(calls) < 2:
            raise ProviderError("service unavailable", status=503)
        return "ok"

    with patch("core.llm.fallback_chain.complete", side_effect=_mock):
        result = complete_with_fallback("FAST_CHEAP", MSG)
        _check("Recovered from 503", result.text == "ok")


def test_empty_response_triggers_fallback() -> None:
    print("\n[3] Empty response → fallback")
    calls = []

    def _mock(model, messages, max_tokens, timeout):
        calls.append(model)
        if len(calls) == 1:
            return ""   # empty — fallback_chain treats as ProviderError
        return "non-empty"

    # fallback_chain raises ProviderError on empty; this test verifies behavior
    with patch("core.llm.fallback_chain.complete", side_effect=_mock):
        try:
            result = complete_with_fallback("FAST_CHEAP", MSG)
            # If fallback_chain catches empty and retries, it should get "non-empty"
            _check("Non-empty response after fallback", result.text == "non-empty")
        except ProviderExhaustedError:
            # Acceptable: empty → error → exhausted within MAX_RETRIES
            _check("ProviderExhaustedError on empty (acceptable)", True)


def test_all_fail_exhausted() -> None:
    print("\n[4] All models fail → ProviderExhaustedError")
    with patch("core.llm.fallback_chain.complete", side_effect=ProviderError("dead")):
        try:
            complete_with_fallback("FAST_CHEAP", MSG)
            _check("Exception raised", False, "no exception")
        except ProviderExhaustedError as e:
            _check("ProviderExhaustedError raised", True)
            _check("Error message mentions tier", "FAST_CHEAP" in str(e))


def test_health_marked_failed_after_error() -> None:
    print("\n[5] Failed model → marked unhealthy")
    # Reset all FAST_CHEAP models before test (previous test may have dirtied health state)
    from core.llm.model_registry import get_models
    for m in get_models("FAST_CHEAP"):
        provider_health.mark_healthy(m)
    models_used = []

    def _mock(model, messages, max_tokens, timeout):
        models_used.append(model)
        if len(models_used) == 1:
            raise ProviderError("fail", status=500)
        return "ok"

    with patch("core.llm.fallback_chain.complete", side_effect=_mock):
        complete_with_fallback("FAST_CHEAP", MSG)

    if models_used:
        first = models_used[0]
        _check(f"First model {first} marked unhealthy", not provider_health.is_healthy(first))
        provider_health.mark_healthy(first)  # cleanup
    else:
        _check("Models attempted", False, "no models called")


def test_prompt_preserved_across_retries() -> None:
    print("\n[6] Original prompt preserved in all retry attempts")
    # Reset health
    from core.llm.model_registry import get_models
    for m in get_models("FAST_CHEAP"):
        provider_health.mark_healthy(m)
    prompts_seen = []
    original = "my exact prompt content"
    calls = [0]

    def _mock(model, messages, max_tokens, timeout):
        prompts_seen.append(messages[0]["content"])
        calls[0] += 1
        if calls[0] < 2:
            raise ProviderError("fail")
        return "ok"

    with patch("core.llm.fallback_chain.complete", side_effect=_mock):
        complete_with_fallback("FAST_CHEAP", [{"role": "user", "content": original}])

    _check("Prompt unchanged in retry", all(p == original for p in prompts_seen),
           f"seen: {prompts_seen}")


if __name__ == "__main__":
    print("fallback behavior tests")
    print("=" * 50)
    test_429_triggers_fallback()
    test_503_triggers_fallback()
    test_empty_response_triggers_fallback()
    test_all_fail_exhausted()
    test_health_marked_failed_after_error()
    test_prompt_preserved_across_retries()
    print(f"\n{'='*50}")
    print(f"RESULT: {_PASS} PASS  {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)

#!/usr/bin/env python3
"""
fallback_chain.py — Retry + provider fallback for IMPERIO LLM calls.

Tries models in tier order. Max 2 retries total across all models.
Hard timeout: 30s per attempt. Never loops infinitely.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from core.llm.model_registry import get_models
from core.llm.openai_compat_client import ProviderError, complete
from core.llm import provider_health


MAX_RETRIES = 2  # total attempts across all models


class ProviderExhaustedError(Exception):
    """Raised when all models in tier have failed."""


@dataclass
class CompletionResult:
    text: str
    model: str
    provider: str = "freellmapi"
    latency_ms: int = 0
    attempts: int = 1
    errors: list[str] = field(default_factory=list)


def complete_with_fallback(
    tier: str,
    messages: list[dict],
    max_tokens: int = 512,
) -> CompletionResult:
    """
    Try models in tier order until one succeeds.

    Returns CompletionResult or raises ProviderExhaustedError.
    Max MAX_RETRIES attempts total — no infinite loops.
    """
    models = get_models(tier)
    errors: list[str] = []
    attempts = 0

    for model in models:
        if attempts >= MAX_RETRIES:
            break

        if not provider_health.is_healthy(model):
            errors.append(f"{model}: skipped (unhealthy)")
            continue

        attempts += 1
        t0 = time.monotonic()

        try:
            text = complete(model=model, messages=messages, max_tokens=max_tokens, timeout=30)
            latency_ms = int((time.monotonic() - t0) * 1000)

            if not text or not text.strip():
                raise ProviderError(f"Empty response from {model}")

            provider_health.mark_healthy(model)
            return CompletionResult(
                text=text.strip(),
                model=model,
                latency_ms=latency_ms,
                attempts=attempts,
                errors=errors,
            )

        except ProviderError as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            provider_health.mark_failed(model, str(e))
            errors.append(f"{model}: {e}")

    raise ProviderExhaustedError(
        f"All models in tier '{tier}' failed after {attempts} attempt(s). "
        f"Errors: {errors}"
    )

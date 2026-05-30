#!/usr/bin/env python3
"""
schemas.py — Frozen dataclasses for inference dispatch layer.

All dataclasses are frozen=True — immutable after construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TaskRequest:
    """
    Request object for a single inference task.

    task_type: one of VALID_TASK_TYPES from task_classifier
    payload:   dict with at minimum {"prompt": str}
    max_tokens: max response tokens
    task_id:   optional trace ID for log correlation
    """
    task_type:  str
    payload:    dict
    max_tokens: int  = 512
    task_id:    str  = ""


@dataclass(frozen=True)
class InferenceResult:
    """
    Result from dispatch(). Never raises — errors surface here.

    success=False means all providers failed; text="" and error set.
    fallback_triggered=True means primary chain failed, fell back to freellmapi.
    """
    text:                str
    task_type:           str
    provider_used:       str
    model_used:          str
    latency_ms:          int
    attempts:            int
    success:             bool
    error:               str   = ""
    fallback_triggered:  bool  = False


@dataclass(frozen=True)
class ProviderStatus:
    """
    Availability status for a single provider.

    available=True if API key is present AND provider is healthy (not in cooldown).
    reason: "ok" | "no_key" | "unhealthy" | "unknown"
    """
    provider_id: str
    available:   bool
    reason:      str = ""


@dataclass(frozen=True)
class FailoverEvent:
    """
    Single failover event — written to logs/inference_failover/YYYY-MM-DD.jsonl.

    Append-only. Never mutate existing entries.
    """
    ts:             str   # ISO UTC timestamp
    task_type:      str
    task_id:        str
    provider_tried: str
    model_tried:    str
    error:          str
    fallback_to:    str   # next provider attempted, or "freellmapi" or "exhausted"

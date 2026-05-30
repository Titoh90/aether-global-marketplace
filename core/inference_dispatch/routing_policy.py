#!/usr/bin/env python3
"""
routing_policy.py — Task-type to provider chain mapping.

TASK_ROUTING and TASK_TO_TIER are MappingProxyType — frozen at import time.
No runtime mutation possible.

Rules:
- "memory_retrieval" and "embedding_generation" chain = ["local"] ONLY.
- freellmapi is always the last resort in non-local chains.
- get_provider_chain() filters to currently available providers.
"""

from __future__ import annotations

from types import MappingProxyType

# ── Routing definitions ───────────────────────────────────────────────────────
# NOTE: groq and gemini removed from chains because API keys are not configured.
# To re-enable: set GROQ_API_KEY / GEMINI_API_KEY via launchctl or .env, then add back to chains.
# All chains now default to openrouter (free llama) → freellmapi (last resort).

_TASK_ROUTING_DEF: dict[str, list[str]] = {
    "caption_generation":   ["openrouter", "freellmapi"],           # openrouter primary (free llama), freellmapi last resort
    "visual_analysis":      ["openrouter", "freellmapi"],           # gemini needs key → openrouter fallback
    "embedding_generation": ["local"],                               # LOCAL ONLY
    "reasoning":            ["openrouter", "freellmapi"],
    "tool_selection":       ["openrouter", "freellmapi"],           # groq needs key → openrouter
    "summarization":        ["openrouter", "freellmapi"],
    "memory_retrieval":     ["local"],                               # LOCAL ONLY
    "trend_analysis":       ["openrouter", "freellmapi"],
    "classification":       ["openrouter", "freellmapi"],           # groq needs key → openrouter
    "prompt_optimization":  ["openrouter", "freellmapi"],
}

_TASK_TO_TIER_DEF: dict[str, str] = {
    "caption_generation":   "FAST_CHEAP",
    "visual_analysis":      "HIGH_REASONING",
    "reasoning":            "HIGH_REASONING",
    "tool_selection":       "FAST_CHEAP",
    "summarization":        "FAST_CHEAP",
    "trend_analysis":       "HIGH_REASONING",
    "classification":       "FAST_CHEAP",
    "prompt_optimization":  "HIGH_REASONING",
    # embedding_generation and memory_retrieval: local-only, no tier needed
}

# Freeze
TASK_ROUTING: MappingProxyType  = MappingProxyType(_TASK_ROUTING_DEF)
TASK_TO_TIER: MappingProxyType  = MappingProxyType(_TASK_TO_TIER_DEF)

# Local-only task types — these must NEVER call external providers
LOCAL_ONLY_TASKS: frozenset[str] = frozenset({"memory_retrieval", "embedding_generation"})


# ── Public API ────────────────────────────────────────────────────────────────

def get_provider_chain(task_type: str) -> list[str]:
    """
    Return the ordered list of available providers for a task_type.

    For local-only tasks: always returns ["local"].
    For other tasks: filters chain to currently available providers,
    always keeping "freellmapi" at the end as last resort if available.
    """
    chain = list(TASK_ROUTING.get(task_type, ["openrouter", "freellmapi"]))

    if task_type in LOCAL_ONLY_TASKS:
        return ["local"]

    from core.inference_dispatch.provider_registry import is_available

    available_chain = [p for p in chain if is_available(p).available]

    # Ensure freellmapi is always at the end if not already in chain
    if "freellmapi" not in available_chain and is_available("freellmapi").available:
        available_chain.append("freellmapi")

    return available_chain


def get_freellmapi_tier(task_type: str) -> str:
    """
    Return the freellmapi tier for a task_type (used as last-resort fallback).
    Defaults to FAST_CHEAP if task_type not in mapping.
    """
    return TASK_TO_TIER.get(task_type, "FAST_CHEAP")


def is_local_only(task_type: str) -> bool:
    """Return True if task_type must only use local processing."""
    return task_type in LOCAL_ONLY_TASKS

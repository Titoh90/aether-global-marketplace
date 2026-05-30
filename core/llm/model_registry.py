#!/usr/bin/env python3
"""
model_registry.py — Model capability tiers for IMPERIO LLM routing.

Tiers list models in priority order (first = most preferred).
freellmapi uses model aliases directly; update here as providers change.
"""

from __future__ import annotations

# Model IDs as recognized by freellmapi / OpenAI-compatible endpoint.
# freellmapi's router maps these to actual provider models.

TIERS: dict[str, list[str]] = {
    # Complex reasoning: analysis, strategy, multi-step logic
    "HIGH_REASONING": [
        "deepseek/deepseek-r1",
        "google/gemini-2.5-flash",
        "google/gemini-pro-1.5",
        "meta-llama/llama-3.3-70b-instruct",
        "auto",  # freellmapi auto-select fallback
    ],

    # Fast + cheap: copy generation, captions, short tasks
    "FAST_CHEAP": [
        "google/gemini-flash-1.5",
        "google/gemini-2.5-flash",
        "qwen/qwen-2.5-72b-instruct",
        "meta-llama/llama-3.1-8b-instruct",
        "auto",
    ],

    # Best instruction following for image prompt generation
    "IMAGE_PROMPTS": [
        "meta-llama/llama-3.3-70b-instruct",
        "google/gemini-2.5-flash",
        "qwen/qwen-2.5-72b-instruct",
        "auto",
    ],

    # Long context: campaigns analysis, bulk product processing
    "LONG_CONTEXT": [
        "google/gemini-pro-1.5",        # 1M context
        "google/gemini-flash-1.5",      # 1M context
        "meta-llama/llama-3.3-70b-instruct",
        "auto",
    ],
}

VALID_TIERS = set(TIERS.keys())


def get_models(tier: str) -> list[str]:
    """Return model list for tier. Raises KeyError on unknown tier."""
    if tier not in TIERS:
        raise KeyError(f"Unknown tier '{tier}'. Valid: {sorted(VALID_TIERS)}")
    return TIERS[tier]

#!/usr/bin/env python3
"""
task_classifier.py — Task type validation and inference for inference dispatch.

VALID_TASK_TYPES is a frozenset — immutable. No runtime additions.
"""

from __future__ import annotations

VALID_TASK_TYPES: frozenset[str] = frozenset({
    "caption_generation",
    "visual_analysis",
    "embedding_generation",
    "reasoning",
    "tool_selection",
    "summarization",
    "memory_retrieval",
    "trend_analysis",
    "classification",
    "prompt_optimization",
})

# Payload heuristics for infer_task_type
_IMAGE_KEYS   = frozenset({"image", "image_url", "image_path", "image_base64", "image_bytes"})
_REASON_KEYS  = frozenset({"steps", "chain_of_thought", "multi_step", "analyze"})
_EMBED_KEYS   = frozenset({"embed", "embedding", "vectorize"})


def classify(task_type: str) -> str:
    """
    Validate and normalize task_type.

    Normalizes to lowercase and strips whitespace.
    Raises ValueError if task_type is not in VALID_TASK_TYPES.
    """
    normalized = task_type.lower().strip()
    if normalized not in VALID_TASK_TYPES:
        raise ValueError(
            f"Unknown task_type '{task_type}'. "
            f"Valid types: {sorted(VALID_TASK_TYPES)}"
        )
    return normalized


def infer_task_type(payload: dict) -> str:
    """
    Heuristically infer task_type from payload when not provided.

    Priority order:
    1. If payload has image keys → visual_analysis
    2. If payload has embedding keys → embedding_generation
    3. If payload has reasoning keys → reasoning
    4. Default → caption_generation (most common task)
    """
    keys = set(payload.keys())

    if keys & _IMAGE_KEYS:
        return "visual_analysis"

    if keys & _EMBED_KEYS:
        return "embedding_generation"

    prompt = str(payload.get("prompt", ""))
    if keys & _REASON_KEYS or len(prompt) > 800:
        return "reasoning"

    return "caption_generation"

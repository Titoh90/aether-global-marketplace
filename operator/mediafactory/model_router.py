from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSelection:
    backend: str
    model: str
    reason: str


def choose_model_backend(task_kind: str) -> ModelSelection:
    normalized = task_kind.strip().lower()

    if normalized == "classification":
        return ModelSelection(
            backend="ollama",
            model="qwen2.5:1.5b",
            reason="Local cheap routing for simple classification tasks.",
        )

    if normalized == "prompt_refine":
        return ModelSelection(
            backend="openrouter",
            model="openrouter/free",
            reason="Free general-purpose prompt refinement and ideation.",
        )

    if normalized == "coding":
        return ModelSelection(
            backend="nvidia",
            model="qwen/qwen3-coder-480b-a35b-instruct",
            reason="Best free coding-oriented backend available for agentic work.",
        )

    return ModelSelection(
        backend="ollama",
        model="qwen2.5:1.5b",
        reason="Fallback local backend for unknown or low-risk tasks.",
    )

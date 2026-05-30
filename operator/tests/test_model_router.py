from __future__ import annotations

from mediafactory.model_router import ModelSelection, choose_model_backend


def test_choose_model_backend_routes_classification_to_ollama() -> None:
    result = choose_model_backend(task_kind="classification")

    assert result == ModelSelection(
        backend="ollama",
        model="qwen2.5:1.5b",
        reason="Local cheap routing for simple classification tasks.",
    )


def test_choose_model_backend_routes_prompt_refine_to_openrouter_free() -> None:
    result = choose_model_backend(task_kind="prompt_refine")

    assert result == ModelSelection(
        backend="openrouter",
        model="openrouter/free",
        reason="Free general-purpose prompt refinement and ideation.",
    )


def test_choose_model_backend_routes_coding_to_nvidia() -> None:
    result = choose_model_backend(task_kind="coding")

    assert result == ModelSelection(
        backend="nvidia",
        model="qwen/qwen3-coder-480b-a35b-instruct",
        reason="Best free coding-oriented backend available for agentic work.",
    )


def test_choose_model_backend_falls_back_to_ollama_for_unknown_tasks() -> None:
    result = choose_model_backend(task_kind="unknown")

    assert result == ModelSelection(
        backend="ollama",
        model="qwen2.5:1.5b",
        reason="Fallback local backend for unknown or low-risk tasks.",
    )

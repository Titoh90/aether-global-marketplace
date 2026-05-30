"""
inference_dispatch — Centralized AI inference routing for IMPERIO.

PUBLIC API:
    from core.inference_dispatch.dispatch import dispatch

RULES:
- ALL AI inference calls go through dispatch(task_type, payload).
- NO module calls providers directly (no anthropic.Chat(), no groq.Client(), etc.)
- memory_retrieval and embedding_generation are ALWAYS local-only.
- dispatch() never raises exceptions to the caller — always returns InferenceResult.
"""

from core.inference_dispatch.dispatch import dispatch
from core.inference_dispatch.schemas import (
    TaskRequest,
    InferenceResult,
    ProviderStatus,
    FailoverEvent,
)

__all__ = [
    "dispatch",
    "TaskRequest",
    "InferenceResult",
    "ProviderStatus",
    "FailoverEvent",
]

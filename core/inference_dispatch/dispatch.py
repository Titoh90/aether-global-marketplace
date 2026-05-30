#!/usr/bin/env python3
"""
dispatch.py — Public API for IMPERIO inference dispatch layer.

USAGE:
    from core.inference_dispatch.dispatch import dispatch

    result = dispatch("caption_generation", {"prompt": "Write a hook for Owala"})
    print(result.text)          # response
    print(result.provider_used) # "openrouter" | "groq" | "freellmapi" | ...
    print(result.success)       # True/False

RULES:
- dispatch() NEVER raises exceptions — always returns InferenceResult.
- memory_retrieval: local ONLY — use core/knowledge_core/retrieval_engine.search_memory() instead.
- embedding_generation: local ONLY — use core/knowledge_core/embedding_cache.get_embedding() instead.
- ALL other task types go through provider fallback chain.
- Logs every call to logs/llm/YYYY-MM-DD.jsonl via core/llm/provider_router.
"""

from __future__ import annotations

import datetime
import json
import sys
import time
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.inference_dispatch.schemas import InferenceResult
from core.inference_dispatch.task_classifier import classify
from core.inference_dispatch.routing_policy import is_local_only
from core.inference_dispatch.fallback_chain import complete_with_task_fallback

# Auto-persist dispatch learnings to knowledge core (non-blocking, best-effort)
try:
    from core.knowledge_core.semantic_memory import persist_learning
except ImportError:
    def persist_learning(content, memory_type, tags=None, source="auto"):
        pass  # knowledge_core not available — skip silently

_LOG_DIR = _IMPERIO_ROOT / "logs" / "llm"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


def _log(entry: dict) -> None:
    """Append JSON line to today's dispatch log. Silent on failure."""
    try:
        date_str = datetime.date.today().isoformat()
        log_file = _LOG_DIR / f"dispatch_{date_str}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def dispatch(
    task_type: str,
    payload: dict,
    max_tokens: int = 512,
    task_id: str = "",
) -> InferenceResult:
    """
    Central entry point for ALL AI inference in IMPERIO.

    Args:
        task_type: one of VALID_TASK_TYPES (caption_generation, reasoning, etc.)
        payload:   dict with at minimum {"prompt": str}
        max_tokens: max response tokens
        task_id:   optional trace ID

    Returns:
        InferenceResult — never raises. Check .success and .error.

    Local-only tasks:
        - "memory_retrieval" → returns error result; use retrieval_engine.search_memory()
        - "embedding_generation" → returns error result; use embedding_cache.get_embedding()
    """
    t0 = time.monotonic()

    # ── Validate task_type ────────────────────────────────────────────────────
    try:
        normalized_type = classify(task_type)
    except ValueError as e:
        return InferenceResult(
            text="",
            task_type=task_type,
            provider_used="none",
            model_used="none",
            latency_ms=0,
            attempts=0,
            success=False,
            error=str(e),
        )

    # ── Local-only gate ───────────────────────────────────────────────────────
    if is_local_only(normalized_type):
        msg = (
            f"task_type '{normalized_type}' is local-only. "
            f"Use core/knowledge_core/retrieval_engine.search_memory() for memory_retrieval, "
            f"or embedding_cache.get_embedding() for embedding_generation."
        )
        return InferenceResult(
            text="",
            task_type=normalized_type,
            provider_used="local",
            model_used="local",
            latency_ms=0,
            attempts=0,
            success=False,
            error=msg,
        )

    # ── Extract prompt ────────────────────────────────────────────────────────
    prompt = payload.get("prompt", "")
    if not prompt:
        prompt = str(payload)  # fallback: serialize full payload as prompt

    # ── Dispatch through fallback chain ───────────────────────────────────────
    try:
        result = complete_with_task_fallback(
            task_type=normalized_type,
            prompt=prompt,
            max_tokens=max_tokens,
            task_id=task_id,
        )
    except Exception as e:
        # Should never happen (fallback_chain catches everything), but just in case
        latency_ms = int((time.monotonic() - t0) * 1000)
        result = InferenceResult(
            text="",
            task_type=normalized_type,
            provider_used="none",
            model_used="none",
            latency_ms=latency_ms,
            attempts=0,
            success=False,
            error=f"Unexpected dispatch error: {e}",
        )

    # ── Log the dispatch (with trace_id for correlation) ────────────────────
    try:
        from core.observability.correlation import get_current_trace
        _trace_id = get_current_trace()
    except Exception:
        _trace_id = None
    _log({
        "ts":               datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "trace_id":         _trace_id or task_id or "",
        "task_type":        normalized_type,
        "task_id":          task_id,
        "provider_used":    result.provider_used,
        "model_used":       result.model_used,
        "latency_ms":       result.latency_ms,
        "attempts":         result.attempts,
        "success":          result.success,
        "fallback":         result.fallback_triggered,
        "tokens_est":       len(result.text.split()) if result.text else 0,
        "error":            result.error[:200] if result.error else "",
    })

    # ── Auto-persist learnings ───────────────────────────────────────────────
    if result.success and result.fallback_triggered:
        persist_learning(
            content=f"Task '{normalized_type}' succeeded via {result.provider_used}/{result.model_used} "
                     f"after {result.attempts} attempt(s) in {result.latency_ms}ms. "
                     f"Primary provider failed — fallback was triggered.",
            memory_type="provider_reliability",
            tags=[normalized_type, result.provider_used, "fallback_recovery"],
            source="dispatch",
        )
    elif not result.success:
        persist_learning(
            content=f"Task '{normalized_type}' FAILED: {result.error[:300]}. "
                     f"Provider={result.provider_used} attempts={result.attempts}.",
            memory_type="failure",
            tags=[normalized_type, "dispatch_failure"],
            source="dispatch",
        )

    return result

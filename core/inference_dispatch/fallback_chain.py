#!/usr/bin/env python3
"""
fallback_chain.py — Task-aware provider fallback chain for inference dispatch.

Strategy:
1. Build available provider chain for task_type via routing_policy.
2. Try each provider in order, max MAX_RETRIES total attempts.
3. On failure: log failover event, mark provider unhealthy, try next.
4. If all direct providers fail: fall back to core/llm/llm_complete() via freellmapi.
5. If freellmapi also fails: return error InferenceResult (never raise).
"""

from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request
import json
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.inference_dispatch.schemas import InferenceResult
from core.inference_dispatch.routing_policy import get_provider_chain, get_freellmapi_tier, is_local_only
from core.inference_dispatch import provider_health as ph
from core.inference_dispatch.provider_registry import get_models, get_base_url, get_api_key
from core.llm.provider_router import llm_complete

# Auto-persist provider events to knowledge core (non-blocking, best-effort)
try:
    from core.knowledge_core.semantic_memory import persist_provider_event
except ImportError:
    def persist_provider_event(provider, event_type, details):
        pass  # knowledge_core not available — skip silently

MAX_RETRIES = 3  # total provider attempts before falling back to freellmapi


# ── Provider call ─────────────────────────────────────────────────────────────

def _call_openai_compat(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    max_tokens: int,
    timeout: int = 30,
) -> str:
    """
    Generic OpenAI-compatible chat completion call via stdlib urllib.
    Returns response text or raises Exception.
    """
    url     = base_url.rstrip("/") + "/chat/completions"
    payload = json.dumps({
        "model":      model,
        "messages":   [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    req  = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode(errors="replace")[:200]
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code}: {body}")

    if "error" in data:
        raise RuntimeError(f"Provider error: {data['error']}")

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected response: {e} — {str(data)[:200]}")


# ── Fallback chain ────────────────────────────────────────────────────────────

def complete_with_task_fallback(
    task_type: str,
    prompt: str,
    max_tokens: int = 512,
    task_id: str = "",
) -> InferenceResult:
    """
    Try providers in task-type chain order, fall back to freellmapi.

    Returns InferenceResult — never raises.
    """
    if is_local_only(task_type):
        return InferenceResult(
            text="",
            task_type=task_type,
            provider_used="local",
            model_used="local",
            latency_ms=0,
            attempts=0,
            success=False,
            error=f"task_type '{task_type}' is local-only — cannot call external provider",
        )

    chain     = get_provider_chain(task_type)
    attempts  = 0
    t_global  = time.monotonic()

    for provider_id in chain:
        if provider_id == "local":
            continue
        if attempts >= MAX_RETRIES:
            break
        if not ph.is_healthy(provider_id):
            continue

        base_url = get_base_url(provider_id)
        api_key  = get_api_key(provider_id)
        models   = get_models(provider_id)

        if not models or base_url in ("", "direct", "local"):
            continue

        model = models[0]
        attempts += 1
        t0 = time.monotonic()

        try:
            text       = _call_openai_compat(base_url, api_key, model, prompt, max_tokens)
            latency_ms = int((time.monotonic() - t0) * 1000)
            ph.mark_healthy(provider_id)
            # Auto-persist provider success (especially important after fallback)
            if attempts > 1:
                persist_provider_event(
                    provider=provider_id,
                    event_type="recovery",
                    details=f"task={task_type} model={model} latency={latency_ms}ms after {attempts} attempt(s)",
                )
            return InferenceResult(
                text=text,
                task_type=task_type,
                provider_used=provider_id,
                model_used=model,
                latency_ms=latency_ms,
                attempts=attempts,
                success=True,
                fallback_triggered=(attempts > 1),
            )
        except Exception as e:
            latency_ms = int((time.monotonic() - t0) * 1000)
            next_p     = chain[chain.index(provider_id) + 1] if chain.index(provider_id) + 1 < len(chain) else "freellmapi"
            ph.emit_failover(
                task_type=task_type,
                task_id=task_id,
                provider_tried=provider_id,
                model_tried=model,
                error=str(e),
                fallback_to=next_p,
            )
            # Auto-persist provider failure to knowledge core
            persist_provider_event(
                provider=provider_id,
                event_type="failure",
                details=f"task={task_type} model={model} error={str(e)[:150]} fallback_to={next_p}",
            )
            continue

    # ── Last resort: freellmapi via core/llm ─────────────────────────────────
    tier = get_freellmapi_tier(task_type)
    t0   = time.monotonic()
    try:
        from core.llm.fallback_chain import ProviderExhaustedError
        result     = llm_complete(prompt=prompt, tier=tier, max_tokens=max_tokens, task_type=task_type)
        latency_ms = int((time.monotonic() - t0) * 1000)
        return InferenceResult(
            text=result.text,
            task_type=task_type,
            provider_used="freellmapi",
            model_used=result.model,
            latency_ms=latency_ms,
            attempts=attempts + 1,
            success=True,
            fallback_triggered=True,
        )
    except Exception as e:
        latency_ms    = int((time.monotonic() - t_global) * 1000)
        ph.emit_failover(
            task_type=task_type,
            task_id=task_id,
            provider_tried="freellmapi",
            model_tried="auto",
            error=str(e),
            fallback_to="exhausted",
        )
        persist_provider_event(
            provider="all",
            event_type="exhausted",
            details=f"task={task_type} ALL providers failed after {attempts + 1} attempt(s): {str(e)[:150]}",
        )
        return InferenceResult(
            text="",
            task_type=task_type,
            provider_used="exhausted",
            model_used="none",
            latency_ms=latency_ms,
            attempts=attempts + 1,
            success=False,
            error=f"All providers exhausted for task_type '{task_type}': {e}",
            fallback_triggered=True,
        )

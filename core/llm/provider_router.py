#!/usr/bin/env python3
"""
provider_router.py — Public API for all LLM calls in IMPERIO.

USAGE (the ONLY import any IMPERIO module should need):

    from core.llm.provider_router import llm_complete

    result = llm_complete(
        prompt="Write a product hook for Owala water bottle",
        tier="FAST_CHEAP",
        max_tokens=200,
        task_type="copy",
    )
    print(result.text)    # response string
    print(result.model)   # model used
    print(result.latency_ms)

RULES:
- ZERO modifications to Truth Layer data (prices, URLs, affiliate links, etc.)
- Provider layer is a pass-through: prompt in → text out
- Logs every call to logs/llm/YYYY-MM-DD.jsonl
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

# Resolve IMPERIO_ROOT for log path
_IMPERIO_ROOT = Path(__file__).parent.parent.parent
_LOG_DIR = _IMPERIO_ROOT / "logs" / "llm"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# Add IMPERIO_ROOT to sys.path if needed
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.llm.fallback_chain import (
    CompletionResult,
    ProviderExhaustedError,
    complete_with_fallback,
)


@dataclass
class LLMResult:
    text: str
    model: str
    provider: str = "freellmapi"
    latency_ms: int = 0
    attempts: int = 1
    tier: str = ""
    task_type: str = ""
    success: bool = True
    error: str = ""


def _log(entry: dict) -> None:
    """Append JSON line to today's log file. Silent on failure."""
    try:
        date_str = datetime.date.today().isoformat()
        log_file = _LOG_DIR / f"{date_str}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def _to_messages(prompt: Union[str, list[dict]]) -> list[dict]:
    """Convert str prompt to messages format."""
    if isinstance(prompt, str):
        return [{"role": "user", "content": prompt}]
    return prompt


def llm_complete(
    prompt: Union[str, list[dict]],
    tier: str = "FAST_CHEAP",
    max_tokens: int = 512,
    task_type: str = "",
) -> LLMResult:
    """
    Route LLM request through freellmapi with automatic fallback.

    Args:
        prompt: str or OpenAI messages list
        tier: "HIGH_REASONING" | "FAST_CHEAP" | "IMAGE_PROMPTS" | "LONG_CONTEXT"
        max_tokens: max response tokens
        task_type: optional label for logs (e.g. "copy", "angle", "caption")

    Returns:
        LLMResult with .text, .model, .latency_ms

    Raises:
        ProviderExhaustedError if all models fail (caller must handle)
    """
    messages = _to_messages(prompt)
    t0 = time.monotonic()

    try:
        result: CompletionResult = complete_with_fallback(
            tier=tier,
            messages=messages,
            max_tokens=max_tokens,
        )
        llm_result = LLMResult(
            text=result.text,
            model=result.model,
            provider=result.provider,
            latency_ms=result.latency_ms,
            attempts=result.attempts,
            tier=tier,
            task_type=task_type,
            success=True,
        )
        # Trace ID for cross-module log correlation
        try:
            from core.observability.correlation import get_current_trace
            _tid = get_current_trace() or ""
        except Exception:
            _tid = ""
        _log({
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "trace_id": _tid,
            "task_type": task_type,
            "tier": tier,
            "model": result.model,
            "provider": result.provider,
            "latency_ms": result.latency_ms,
            "tokens_est": len(result.text.split()),
            "success": True,
            "attempt": result.attempts,
        })
        return llm_result

    except ProviderExhaustedError as e:
        latency_ms = int((time.monotonic() - t0) * 1000)
        try:
            from core.observability.correlation import get_current_trace
            _tid = get_current_trace() or ""
        except Exception:
            _tid = ""
        _log({
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "trace_id": _tid,
            "task_type": task_type,
            "tier": tier,
            "model": "none",
            "provider": "freellmapi",
            "latency_ms": latency_ms,
            "tokens_est": 0,
            "success": False,
            "attempt": 0,
            "error": str(e)[:200],
        })
        raise


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="provider_router smoke test")
    parser.add_argument("--tier", default="FAST_CHEAP")
    parser.add_argument("--prompt", default="Say hello in one sentence.")
    parser.add_argument("--max-tokens", type=int, default=100)
    args = parser.parse_args()

    print(f"Testing tier={args.tier} ...")
    try:
        r = llm_complete(args.prompt, tier=args.tier, max_tokens=args.max_tokens, task_type="test")
        print(f"✅ model={r.model} latency={r.latency_ms}ms")
        print(f"   {r.text[:200]}")
    except ProviderExhaustedError as e:
        print(f"❌ All providers failed: {e}")
        sys.exit(1)

"""
ai_spend_governor.py — Daily LLM API spend tracking and budget enforcement.

Tracks token usage and estimated cost per provider. Enforces daily ceiling.
Degrades gracefully: PROCEED → DOWNGRADE_TIER → BLOCK.

Usage:
    from core.guardrails.ai_spend_governor import check_budget, record_spend

    decision = check_budget("openrouter", estimated_tokens=500)
    if decision == SpendDecision.BLOCK:
        return error_result("daily AI budget exhausted")

    # After successful call:
    record_spend("openrouter", tokens_used=423, cost_usd=0.0001)

Budget ceiling via env var:
    IMPERIO_DAILY_AI_BUDGET_USD=1.00  (default: no limit)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
SPEND_DIR = IMPERIO_ROOT / "logs" / "guardrails"


class SpendDecision(str, Enum):
    PROCEED = "PROCEED"
    DOWNGRADE_TIER = "DOWNGRADE_TIER"
    BLOCK = "BLOCK"


# Approximate cost per 1K tokens (input) by provider — conservative estimates
COST_PER_1K_TOKENS: dict[str, float] = {
    "openrouter": 0.0001,   # free tier models
    "groq": 0.0001,         # free tier
    "gemini": 0.0002,
    "anthropic": 0.003,     # Claude Haiku
    "github_models": 0.0,   # free
    "freellmapi": 0.0,      # local proxy
    "local": 0.0,           # Ollama
}

_lock = Lock()


@dataclass
class DailySpend:
    date: str = ""
    providers: dict[str, dict] = field(default_factory=dict)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    total_calls: int = 0


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def _spend_file(date: str = None) -> Path:
    SPEND_DIR.mkdir(parents=True, exist_ok=True)
    return SPEND_DIR / f"daily_spend_{date or _today()}.json"


def _load_today() -> DailySpend:
    """Load today's spend data."""
    path = _spend_file()
    if not path.exists():
        return DailySpend(date=_today())
    try:
        data = json.loads(path.read_text())
        return DailySpend(
            date=data.get("date", _today()),
            providers=data.get("providers", {}),
            total_tokens=data.get("total_tokens", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            total_calls=data.get("total_calls", 0),
        )
    except (json.JSONDecodeError, KeyError):
        return DailySpend(date=_today())


def _save(spend: DailySpend) -> None:
    """Persist spend data."""
    path = _spend_file(spend.date)
    path.write_text(json.dumps({
        "date": spend.date,
        "providers": spend.providers,
        "total_tokens": spend.total_tokens,
        "total_cost_usd": round(spend.total_cost_usd, 6),
        "total_calls": spend.total_calls,
    }, indent=2))


def _get_budget() -> float:
    """
    Get daily budget ceiling from env var.
    Returns float('inf') if not set (no limit).
    """
    val = os.environ.get("IMPERIO_DAILY_AI_BUDGET_USD", "")
    if not val:
        return float("inf")
    try:
        return float(val)
    except ValueError:
        return float("inf")


def check_budget(
    provider: str,
    estimated_tokens: int = 500,
) -> SpendDecision:
    """
    Check if we can afford this API call within daily budget.

    Returns:
        PROCEED — go ahead
        DOWNGRADE_TIER — budget is 80%+ used, switch to cheaper model
        BLOCK — budget exhausted, do not make the call
    """
    budget = _get_budget()
    if budget == float("inf"):
        return SpendDecision.PROCEED

    with _lock:
        spend = _load_today()
        cost_per_token = COST_PER_1K_TOKENS.get(provider, 0.001) / 1000
        estimated_cost = estimated_tokens * cost_per_token
        projected = spend.total_cost_usd + estimated_cost

        if projected >= budget:
            return SpendDecision.BLOCK
        if projected >= budget * 0.8:
            return SpendDecision.DOWNGRADE_TIER
        return SpendDecision.PROCEED


def record_spend(
    provider: str,
    tokens_used: int,
    cost_usd: float = 0.0,
) -> None:
    """
    Record actual spend after an API call completes.

    If cost_usd is 0, estimates from COST_PER_1K_TOKENS table.
    """
    with _lock:
        spend = _load_today()

        if cost_usd <= 0:
            cost_per_token = COST_PER_1K_TOKENS.get(provider, 0.001) / 1000
            cost_usd = tokens_used * cost_per_token

        if provider not in spend.providers:
            spend.providers[provider] = {
                "tokens": 0, "cost_usd": 0.0, "calls": 0
            }

        spend.providers[provider]["tokens"] += tokens_used
        spend.providers[provider]["cost_usd"] += cost_usd
        spend.providers[provider]["calls"] += 1

        spend.total_tokens += tokens_used
        spend.total_cost_usd += cost_usd
        spend.total_calls += 1

        _save(spend)


def get_daily_spend(date: str = None) -> dict:
    """Get spend summary for a given date (default: today)."""
    with _lock:
        spend = _load_today() if date is None else DailySpend()
        if date:
            path = _spend_file(date)
            if path.exists():
                try:
                    return json.loads(path.read_text())
                except json.JSONDecodeError:
                    pass
        return {
            "date": spend.date,
            "providers": spend.providers,
            "total_tokens": spend.total_tokens,
            "total_cost_usd": round(spend.total_cost_usd, 6),
            "total_calls": spend.total_calls,
            "budget_usd": _get_budget(),
            "budget_remaining": round(_get_budget() - spend.total_cost_usd, 6),
        }

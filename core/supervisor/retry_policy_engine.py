"""
retry_policy_engine.py — Deterministic retry policies per failure type.

Defines how many times and how to retry failed operations.
Respects circuit breaker state — no retries if circuit is OPEN.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RetryDecision(Enum):
    RETRY = "retry"
    SKIP = "skip"
    ESCALATE = "escalate"


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int
    base_delay_seconds: float
    backoff_multiplier: float
    max_delay_seconds: float


# Per-category policies
POLICIES: dict[str, RetryPolicy] = {
    "executor": RetryPolicy(
        max_retries=2,
        base_delay_seconds=30,
        backoff_multiplier=2.0,
        max_delay_seconds=120,
    ),
    "generation": RetryPolicy(
        max_retries=3,
        base_delay_seconds=5,
        backoff_multiplier=1.5,
        max_delay_seconds=30,
    ),
    "api": RetryPolicy(
        max_retries=3,
        base_delay_seconds=2,
        backoff_multiplier=2.0,
        max_delay_seconds=60,
    ),
    "budget": RetryPolicy(
        max_retries=0,  # no retry — wait for next day
        base_delay_seconds=0,
        backoff_multiplier=1,
        max_delay_seconds=0,
    ),
    "system": RetryPolicy(
        max_retries=1,
        base_delay_seconds=10,
        backoff_multiplier=1,
        max_delay_seconds=10,
    ),
}

DEFAULT_POLICY = RetryPolicy(
    max_retries=1,
    base_delay_seconds=5,
    backoff_multiplier=1,
    max_delay_seconds=30,
)


def get_retry_decision(
    category: str,
    attempt: int,
    circuit_open: bool = False,
) -> tuple[RetryDecision, float]:
    """
    Decide whether to retry a failed operation.

    Args:
        category: failure category (executor, generation, api, etc.)
        attempt: current attempt number (0-based)
        circuit_open: whether circuit breaker is open for this executor

    Returns:
        (decision, delay_seconds)
    """
    if circuit_open:
        return RetryDecision.SKIP, 0

    policy = POLICIES.get(category, DEFAULT_POLICY)

    if attempt >= policy.max_retries:
        return RetryDecision.ESCALATE, 0

    delay = min(
        policy.base_delay_seconds * (policy.backoff_multiplier ** attempt),
        policy.max_delay_seconds,
    )

    return RetryDecision.RETRY, delay

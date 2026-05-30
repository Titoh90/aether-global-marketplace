"""
circuit_breaker.py — Per-executor failure tracking with auto-disable.

States:
    CLOSED    → normal operation, executor is healthy
    OPEN      → executor disabled (N consecutive failures)
    HALF_OPEN → cooldown elapsed, next call is a test

Transitions:
    CLOSED  + failure  → increment counter → if count >= threshold → OPEN
    CLOSED  + success  → reset counter
    OPEN    + cooldown → HALF_OPEN
    HALF_OPEN + success → CLOSED
    HALF_OPEN + failure → OPEN (reset cooldown)

Usage:
    from core.guardrails.circuit_breaker import CircuitBreaker

    cb = CircuitBreaker()
    if cb.is_open("instagram"):
        skip_instagram()
    else:
        try:
            post_to_instagram()
            cb.record_success("instagram")
        except Exception as e:
            cb.record_failure("instagram", str(e))
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from threading import Lock

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
STATE_FILE = IMPERIO_ROOT / "logs" / "guardrails" / "circuit_breaker_state.json"


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class ExecutorCircuit:
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    last_failure_time: float = 0.0
    last_failure_error: str = ""
    last_success_time: float = 0.0
    total_failures: int = 0
    total_successes: int = 0


class CircuitBreaker:
    """
    Deterministic circuit breaker. No AI, no LLM. Pure failure counting.
    Thread-safe. Persists state to JSON between runs.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: int = 1800,  # 30 minutes
        state_file: Path = STATE_FILE,
    ):
        self._threshold = failure_threshold
        self._cooldown = cooldown_seconds
        self._state_file = state_file
        self._circuits: dict[str, ExecutorCircuit] = {}
        self._lock = Lock()
        self._load()

    def _load(self) -> None:
        """Load state from JSON file."""
        if not self._state_file.exists():
            return
        try:
            data = json.loads(self._state_file.read_text())
            for name, vals in data.items():
                self._circuits[name] = ExecutorCircuit(
                    state=CircuitState(vals.get("state", "CLOSED")),
                    consecutive_failures=vals.get("consecutive_failures", 0),
                    last_failure_time=vals.get("last_failure_time", 0),
                    last_failure_error=vals.get("last_failure_error", ""),
                    last_success_time=vals.get("last_success_time", 0),
                    total_failures=vals.get("total_failures", 0),
                    total_successes=vals.get("total_successes", 0),
                )
        except (json.JSONDecodeError, KeyError):
            pass

    def _save(self) -> None:
        """Persist state to JSON file."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for name, c in self._circuits.items():
            data[name] = {
                "state": c.state.value,
                "consecutive_failures": c.consecutive_failures,
                "last_failure_time": c.last_failure_time,
                "last_failure_error": c.last_failure_error,
                "last_success_time": c.last_success_time,
                "total_failures": c.total_failures,
                "total_successes": c.total_successes,
            }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _get(self, executor: str) -> ExecutorCircuit:
        if executor not in self._circuits:
            self._circuits[executor] = ExecutorCircuit()
        return self._circuits[executor]

    def record_success(self, executor: str) -> None:
        """Record successful execution. Closes circuit if HALF_OPEN."""
        with self._lock:
            c = self._get(executor)
            c.consecutive_failures = 0
            c.last_success_time = time.time()
            c.total_successes += 1
            c.state = CircuitState.CLOSED
            self._save()

    def record_failure(self, executor: str, error: str) -> None:
        """Record failed execution. Opens circuit after threshold."""
        with self._lock:
            c = self._get(executor)
            c.consecutive_failures += 1
            c.last_failure_time = time.time()
            c.last_failure_error = error[:500]
            c.total_failures += 1

            if c.consecutive_failures >= self._threshold:
                c.state = CircuitState.OPEN

            self._save()

    def is_open(self, executor: str) -> bool:
        """
        Check if executor is disabled.
        Returns True if OPEN (should skip).
        Returns False if CLOSED or HALF_OPEN (should attempt).

        Automatically transitions OPEN → HALF_OPEN after cooldown.
        """
        with self._lock:
            c = self._get(executor)

            if c.state == CircuitState.CLOSED:
                return False

            if c.state == CircuitState.OPEN:
                elapsed = time.time() - c.last_failure_time
                if elapsed >= self._cooldown:
                    c.state = CircuitState.HALF_OPEN
                    self._save()
                    return False  # allow test attempt
                return True  # still in cooldown

            # HALF_OPEN — allow one test attempt
            return False

    def get_status(self) -> dict[str, dict]:
        """Get current state of all circuits."""
        with self._lock:
            result = {}
            for name, c in self._circuits.items():
                # Check for auto-transition
                if c.state == CircuitState.OPEN:
                    elapsed = time.time() - c.last_failure_time
                    if elapsed >= self._cooldown:
                        c.state = CircuitState.HALF_OPEN
                result[name] = {
                    "state": c.state.value,
                    "consecutive_failures": c.consecutive_failures,
                    "total_failures": c.total_failures,
                    "total_successes": c.total_successes,
                    "last_error": c.last_failure_error[:100],
                }
            return result

    def reset(self, executor: str) -> None:
        """Manually reset an executor circuit to CLOSED. Use with caution."""
        with self._lock:
            c = self._get(executor)
            c.state = CircuitState.CLOSED
            c.consecutive_failures = 0
            self._save()

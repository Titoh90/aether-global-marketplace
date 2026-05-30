#!/usr/bin/env python3
"""
failed_generation_registry.py — Registry of failed generations.

Records every failed generation attempt with failure mode classification,
root cause analysis, and recovery patterns. Prevents repeating known-bad
patterns by feeding back into the prompt variation engine.

Teaches the agent: "Don't make the same mistake twice."

SANDBOX-ONLY: Never touches production pipeline.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from core.cinematic_video.sandbox.schemas import (
    FailureEntry,
    _make_id,
    _now_iso,
)


_IMPERIO_ROOT = Path(__file__).parent.parent.parent.parent
_STORE_DIR = _IMPERIO_ROOT / "logs" / "sandbox" / "failures"
_STORE_FILE = _STORE_DIR / "registry.jsonl"


def _ensure_store() -> None:
    _STORE_DIR.mkdir(parents=True, exist_ok=True)


def _load_all() -> list[dict]:
    if not _STORE_FILE.exists():
        return []
    records: list[dict] = []
    try:
        for line in _STORE_FILE.read_text().strip().split("\n"):
            if line.strip():
                records.append(json.loads(line))
    except Exception:
        return []
    return records


def _append(failure: FailureEntry) -> None:
    _ensure_store()
    try:
        with open(_STORE_FILE, "a") as f:
            f.write(json.dumps(failure.to_dict(), ensure_ascii=False) + "\n")
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# Failure mode classification
# ═══════════════════════════════════════════════════════════════════════════════

def _classify_failure(error_message: str, prompt: str) -> tuple[str, str, str]:
    """
    Classify a failure from error message and prompt.

    Returns (failure_mode, root_cause, recovery_suggestion).
    """
    msg_lower = error_message.lower()
    prompt_lower = prompt.lower()

    # Check for known failure patterns
    if "credit" in msg_lower or "quota" in msg_lower or "limit" in msg_lower:
        return (
            "credits_exhausted",
            "Daily credit limit reached. Budget exceeded or credit check not performed before generation.",
            "Wait for daily credit reset. Implement pre-generation credit check. "
            "Reduce experiment batch size or defer less-critical variations.",
        )

    if "timeout" in msg_lower or "timed out" in msg_lower:
        return (
            "generation_timeout",
            "Generation took too long and timed out. Complex prompt or server congestion.",
            "Simplify prompt structure. Reduce prompt length. Retry during off-peak hours.",
        )

    if "reject" in msg_lower or "policy" in msg_lower or "violation" in msg_lower:
        return (
            "prompt_rejected",
            "Prompt rejected by content policy. May contain blocked terms or ambiguous descriptions.",
            "Review prompt for policy-sensitive terms. Use neutral product descriptions. "
            "Avoid brand names, competitor references, or ambiguous language.",
        )

    if "resolution" in msg_lower or "quality" in msg_lower or "blurry" in msg_lower:
        return (
            "resolution_degraded",
            "Output resolution degraded below usable quality threshold.",
            "Use higher-quality reference images. Avoid extreme aspect ratios. "
            "Consider external upscaling in post-production.",
        )

    if "drift" in msg_lower or "style" in msg_lower or "inconsistent" in msg_lower:
        return (
            "style_drift_excessive",
            "Style drift exceeded acceptable threshold. Multiple extensions or "
            "incompatible prompt elements likely caused degradation.",
            "Use frame anchoring (image_to_video with last frame). "
            "Limit extensions to 2 max. Use consistent style keywords across prompts.",
        )

    if "product" in msg_lower and ("recognize" in msg_lower or "fidelity" in msg_lower):
        return (
            "product_fidelity_lost",
            "Product not recognizable in output. Text-to-video may have "
            "reinterpreted the product description too creatively.",
            "Use image_to_video with clean product reference. "
            "Make product description more specific and prominent in prompt.",
        )

    if "camera" in msg_lower or "motion" in msg_lower or "framing" in msg_lower:
        return (
            "camera_motion_wrong",
            "Camera motion did not match specification. AI reinterpretation of camera direction.",
            "Use more explicit camera motion terms. Try alternative motion descriptions. "
            "Test camera motion variants in dry-run first.",
        )

    if "lighting" in msg_lower or "exposure" in msg_lower or "dark" in msg_lower:
        return (
            "lighting_inconsistency",
            "Lighting inconsistent across the clip or doesn't match specification.",
            "Specify EXACT lighting setup. Use reference image for lighting consistency. "
            "Avoid mixing multiple lighting styles in one prompt.",
        )

    if "export" in msg_lower or "download" in msg_lower:
        return (
            "export_failed",
            "Export or download of generated clip failed.",
            "Check network connection. Retry export. Try downloading individual frames "
            "and reassembling externally.",
        )

    if "ui" in msg_lower or "navigate" in msg_lower or "element" in msg_lower:
        return (
            "ui_navigation_error",
            "UI navigation error — element not found or wrong mode selected.",
            "Verify Flow UI state before operation. Check mode/pane is active. "
            "Refresh page and retry.",
        )

    # Unknown failure
    return (
        "unknown_failure",
        f"Unclassified failure: {error_message[:100]}",
        "Document this failure for future classification. Retry with simpler parameters.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def record_failure(
    experiment_id: str,
    variation_id: str,
    error_message: str,
    prompt_used: str = "",
    recovery_attempted: str = "",
    recovery_successful: bool = False,
    permanent: bool = False,
) -> FailureEntry:
    """
    Record a generation failure.

    Auto-classifies failure mode and root cause from the error message.
    Persists to JSONL registry. Never raises.
    """
    failure_mode, root_cause, recovery = _classify_failure(error_message, prompt_used)

    if not recovery_attempted:
        recovery_attempted = recovery

    entry = FailureEntry(
        failure_id=_make_id("fail"),
        experiment_id=experiment_id,
        variation_id=variation_id,
        failure_mode=failure_mode,
        root_cause=root_cause,
        recovery_attempted=recovery_attempted,
        recovery_successful=recovery_successful,
        recorded_at=_now_iso(),
        prompt_used=prompt_used,
        permanent=permanent,
    )

    _append(entry)
    return entry


def get_failures_by_mode(
    failure_mode: str = "",
    limit: int = 50,
) -> tuple[FailureEntry, ...]:
    """
    Retrieve failures, optionally filtered by failure mode.

    Returns most recent first.
    """
    all_data = _load_all()
    entries: list[FailureEntry] = []

    for d in all_data[::-1]:
        if failure_mode and d.get("failure_mode") != failure_mode:
            continue
        entries.append(FailureEntry(
            failure_id=d.get("failure_id", ""),
            experiment_id=d.get("experiment_id", ""),
            variation_id=d.get("variation_id", ""),
            failure_mode=d.get("failure_mode", ""),
            root_cause=d.get("root_cause", ""),
            recovery_attempted=d.get("recovery_attempted", ""),
            recovery_successful=d.get("recovery_successful", False),
            recorded_at=d.get("recorded_at", ""),
            prompt_used=d.get("prompt_used", ""),
            permanent=d.get("permanent", False),
        ))
        if len(entries) >= limit:
            break

    return tuple(entries)


def get_recovery_for_pattern(
    failure_mode: str,
) -> str | None:
    """
    Get the most successful recovery strategy for a given failure mode.

    Returns the recovery text, or None if no successful recoveries found.
    """
    all_data = _load_all()
    recoveries = [
        d for d in all_data
        if d.get("failure_mode") == failure_mode and d.get("recovery_successful")
    ]
    if not recoveries:
        return None
    return recoveries[-1].get("recovery_attempted", "")


def get_failure_statistics() -> dict:
    """
    Get aggregate failure statistics from the registry.

    Returns dict with: total_failures, by_mode, permanent_count, recovery_rate.
    """
    all_data = _load_all()
    if not all_data:
        return {
            "total_failures": 0,
            "by_mode": {},
            "permanent_count": 0,
            "recovery_rate": 0.0,
        }

    modes = Counter(d.get("failure_mode", "unknown") for d in all_data)
    permanent = sum(1 for d in all_data if d.get("permanent"))
    recovered = sum(1 for d in all_data if d.get("recovery_successful"))

    return {
        "total_failures": len(all_data),
        "by_mode": dict(modes.most_common()),
        "permanent_count": permanent,
        "recovery_rate": round(recovered / max(len(all_data), 1), 3),
    }


def clear_failure_registry() -> bool:
    """Clear all failure records. Returns True if successful."""
    try:
        if _STORE_FILE.exists():
            _STORE_FILE.unlink()
        return True
    except Exception:
        return False


__all__ = [
    "record_failure",
    "get_failures_by_mode",
    "get_recovery_for_pattern",
    "get_failure_statistics",
    "clear_failure_registry",
]

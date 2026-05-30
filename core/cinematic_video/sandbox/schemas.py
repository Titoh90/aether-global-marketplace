#!/usr/bin/env python3
"""
schemas.py — Frozen dataclasses for Flow Sandbox Mode.

All types are immutable (frozen=True) and serializable.
Sandbox-only: never touches production pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExperimentConfig:
    """Configuration for a single sandbox experiment."""
    experiment_id:     str
    base_prompt:       str          # the starting prompt
    product_name:      str = ""
    storyboard_id:     str = ""     # reference to storyboard pattern
    variation_count:   int = 4      # how many variations to generate
    extend_count:      int = 3      # how many extensions to test per clip
    dry_run:           bool = True  # True = simulation only, False = real Flow
    max_credits:       int = 8      # credit budget for this experiment
    dimensions:        tuple[str, ...] = ("shot_type", "camera_motion", "lighting")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["dimensions"] = list(self.dimensions)
        return d


# ═══════════════════════════════════════════════════════════════════════════════
# Prompt Variation
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PromptVariation:
    """One systematic variation of a base prompt."""
    variation_id:      str
    base_prompt:       str
    varied_prompt:     str        # the actual prompt text
    dimension:         str        # which variation dimension was changed (shot_type, camera_motion, lighting, etc.)
    change_description: str       # what was altered
    shot_type:         str = ""   # SHOT_TYPE applied
    camera_motion:     str = ""   # CAMERA_MOTION applied
    lighting:          str = ""   # LIGHTING_STYLE applied
    atmosphere:        str = ""   # ATMOSPHERE applied
    lens_style:        str = ""
    pacing:            str = ""
    aspect_ratio:      str = "9:16"
    estimated_credits: int = 1

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
# Extension Trial
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ExtensionTrial:
    """Result of testing extend-mode behavior on a clip."""
    trial_id:          str
    variation_id:      str
    extension_index:   int        # 0 = base, 1 = first extend, 2 = second, etc.
    outcome:           str        # extension outcome (success, degraded, failed, aborted)
    drift_score:       float      # 0.0–1.0 continuity drift estimate
    credit_cost:       int
    issues:            tuple[str, ...]  # problems detected
    recommendation:    str        # "continue" | "stop" | "retry_with_anchor"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["issues"] = list(self.issues)
        return d


# ═══════════════════════════════════════════════════════════════════════════════
# Continuity Record
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ContinuityRecord:
    """One continuity score record — persisted across experiments."""
    record_id:         str
    variation_id:      str
    dimension:         str        # CONTINUITY_DIMENSION
    score:             float      # 0.0–1.0
    recorded_at:       str
    experiment_id:     str
    notes:             str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
# Generation Review
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class GenerationReview:
    """Quality review of a generated output (simulated or real)."""
    review_id:         str
    variation_id:      str
    overall_score:     float      # 0.0–1.0 composite quality
    drift_score:       float      # 0.0–1.0
    fidelity_score:    float      # 0.0–1.0 product accuracy
    aesthetic_score:   float      # 0.0–1.0 visual appeal
    issues:            tuple[str, ...]
    severity:          str        # severity level (info, warning, error, critical)
    recommendation:    str        # "approve" | "retake" | "discard" | "extend"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["issues"] = list(self.issues)
        return d


# ═══════════════════════════════════════════════════════════════════════════════
# Failure Entry
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class FailureEntry:
    """One recorded failure from a sandbox experiment."""
    failure_id:        str
    experiment_id:     str
    variation_id:      str
    failure_mode:      str        # failure mode (style_drift_excessive, credits_exhausted, etc.)
    root_cause:        str        # diagnosed cause
    recovery_attempted: str = ""  # what was tried
    recovery_successful: bool = False
    recorded_at:       str = ""
    prompt_used:       str = ""   # the prompt that triggered this failure
    permanent:         bool = False  # True if this pattern should never be retried

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════════
# Sandbox Experiment (Aggregate)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SandboxExperiment:
    """Complete result of one sandbox experiment."""
    experiment_id:     str
    config:            ExperimentConfig
    variations:        tuple[PromptVariation, ...]
    extension_trials:  tuple[ExtensionTrial, ...]
    continuity_records: tuple[ContinuityRecord, ...]
    reviews:           tuple[GenerationReview, ...]
    failures:          tuple[FailureEntry, ...]
    started_at:        str
    completed_at:      str
    duration_ms:       int
    total_credits_used: int
    best_variation_id: str = ""   # highest-scoring variation
    lessons_learned:   tuple[str, ...] = ()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["config"] = self.config.to_dict()
        d["variations"] = [v.to_dict() for v in self.variations]
        d["extension_trials"] = [t.to_dict() for t in self.extension_trials]
        d["continuity_records"] = [r.to_dict() for r in self.continuity_records]
        d["reviews"] = [r.to_dict() for r in self.reviews]
        d["failures"] = [f.to_dict() for f in self.failures]
        d["lessons_learned"] = list(self.lessons_learned)
        return d


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _make_id(prefix: str) -> str:
    import hashlib
    seed = f"{prefix}_{_now_iso()}"
    return f"{prefix}_{hashlib.sha256(seed.encode()).hexdigest()[:10]}"

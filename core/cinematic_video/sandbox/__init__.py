#!/usr/bin/env python3
"""
sandbox/ — Flow Sandbox Mode (PHASE 5)

EXPERIMENTATION-ONLY: Real Flow operations in a sandboxed environment.
The agent practices, generates, compares, learns, and records results
WITHOUT touching the production pipeline.

Google Flow has:
  - daily credit limits
  - unpredictable degradation
  - non-deterministic behavior
  - UI changes
  - quality variation

The sandbox teaches operational knowledge — not just specs.

Sub-modules:
    schemas.py                      — Frozen dataclasses for sandbox types
    prompt_variation_engine.py      — Systematic prompt variation generation
    clip_extension_tester.py        — Extend-mode boundary testing with drift
    continuity_score_tracker.py     — Persistent continuity scoring across experiments
    generation_reviewer.py          — Quality review of generated outputs
    failed_generation_registry.py   — Failure registry with root cause analysis
    flow_experiment_runner.py       — Main orchestrator connecting all modules

Rules:
    - MAY use real Flow (opt-in) — but results stay in sandbox
    - NEVER modifies production pipeline
    - NEVER touches Truth Layer, Revenue Layer, Dispatch Gate
    - All schemas frozen=True
    - Never raises — always returns results with diagnostics
    - Persistent JSON storage for learning across sessions
"""

from core.cinematic_video.sandbox.schemas import (
    ExperimentConfig,
    PromptVariation,
    ExtensionTrial,
    ContinuityRecord,
    GenerationReview,
    FailureEntry,
    SandboxExperiment,
)

from core.cinematic_video.sandbox.prompt_variation_engine import (
    generate_variations,
    generate_single_variation,
    variation_count_for_dimensions,
)

from core.cinematic_video.sandbox.clip_extension_tester import (
    run_extension_trial,
    batch_extension_trial,
    get_extension_health,
)

from core.cinematic_video.sandbox.continuity_score_tracker import (
    record_continuity_score,
    get_continuity_history,
    get_best_patterns,
    get_dimension_trend,
    clear_continuity_history,
)

from core.cinematic_video.sandbox.generation_reviewer import (
    review_generation,
    batch_review,
    get_review_summary,
)

from core.cinematic_video.sandbox.failed_generation_registry import (
    record_failure,
    get_failures_by_mode,
    get_recovery_for_pattern,
    get_failure_statistics,
    clear_failure_registry,
)

from core.cinematic_video.sandbox.flow_experiment_runner import (
    run_experiment,
    run_batch_experiments,
    get_experiment_history,
)

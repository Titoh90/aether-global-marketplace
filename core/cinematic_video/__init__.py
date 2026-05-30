#!/usr/bin/env python3
"""
cinematic_video — Cinematic Video Research Layer (PHASE 3)

LEARNING-ONLY: No video generation. No pipeline modification.
Builds structured knowledge of Google Flow's cinematographic capabilities.

Sub-modules:
    research/
        schemas.py                  — Frozen dataclasses for all cinematic types
        flow_feature_registry.py    — 14 Flow features documented
        flow_ui_mapper.py           — 14 Flow UI elements mapped
        camera_motion_library.py    — 16 camera movements cataloged
        scene_transition_library.py — 10 transition types
        continuity_rules.py         — 8 continuity rules
        prompt_cinema_patterns.py   — 7 prompt structure patterns
        shot_taxonomy.py            — 12 shot types
        flow_limitations.py         — 12 documented Flow limitations
        storyboard_patterns.py      — 5 multi-shot storyboard patterns
        generation_cost_estimator.py — Credit optimization engine
        video_continuity_validator.py — Continuity scoring (non-blocking)
    flow_operator_training/
        schemas.py, training_exercises.py, workflow_simulator.py,
        exercise_validator.py       — 24 exercises across 4 levels
    sandbox/                        — PHASE 5: Flow Sandbox Mode
        schemas.py                  — Frozen dataclasses for sandbox types
        prompt_variation_engine.py  — Systematic prompt variation generator
        clip_extension_tester.py    — Extend-mode boundary testing with drift
        continuity_score_tracker.py — Persistent continuity scoring
        generation_reviewer.py      — Quality review of generated outputs
        failed_generation_registry.py — Failure registry with root cause analysis
        flow_experiment_runner.py   — Main experiment orchestrator

Rules:
    - NO video generation in this layer
    - NO Flow API calls
    - NO pipeline modification
    - NEVER modifies runtime critical path
    - NEVER touches Truth Layer, Revenue Layer, Dispatch Gate
    - Pure knowledge + validation logic
    - All AI calls through dispatch() only
    - Never raises — always returns results with warnings
    - All schemas frozen=True
"""

from core.cinematic_video.research.flow_feature_registry import (
    get_all_features,
    get_feature,
    get_features_by_mode,
    get_high_risk_features,
    get_credit_efficient_features,
    feature_count,
)
from core.cinematic_video.research.camera_motion_library import (
    get_all_motions,
    get_motion,
    get_motions_by_emotion,
    get_motions_for_product,
    get_motions_by_speed,
    motion_count,
)
from core.cinematic_video.research.shot_taxonomy import (
    get_all_shots,
    get_shot,
    get_shots_by_aesthetic,
    get_shots_by_pacing,
    get_shots_by_category,
    get_compatible_shots,
    shot_count,
)
from core.cinematic_video.research.scene_transition_library import (
    get_all_transitions,
    get_transition,
    get_transitions_by_complexity,
    get_low_drift_transitions,
    get_transitions_for_shot,
    transition_count,
)
from core.cinematic_video.research.continuity_rules import (
    get_all_rules,
    get_rule,
    get_rules_by_dimension,
    get_rules_for_mode,
    rule_count,
)
from core.cinematic_video.research.prompt_cinema_patterns import (
    get_all_patterns,
    get_pattern,
    get_patterns_for_shot,
    get_strongest_pattern,
    pattern_count,
)
from core.cinematic_video.research.storyboard_patterns import (
    get_all_storyboards,
    get_storyboard,
    get_storyboards_for_product,
    get_storyboards_by_risk,
    storyboard_count,
)
from core.cinematic_video.research.flow_limitations import (
    get_all_limitations,
    get_limitation,
    get_critical_limitations,
    get_limitations_by_mode,
    limitation_count,
)
from core.cinematic_video.research.flow_ui_mapper import (
    get_all_elements,
    get_element,
    get_elements_by_mode,
    ui_element_count,
)
from core.cinematic_video.research.generation_cost_estimator import (
    estimate_cost,
    should_use_image_first,
    should_extend_instead_of_new_clip,
    should_reuse_frame,
    should_abort_sequence,
    is_storyboard_too_risky,
    _DEFAULT_DAILY_BUDGET,
)
from core.cinematic_video.research.video_continuity_validator import (
    validate_storyboard_continuity,
)

from core.cinematic_video.flow_operator_training.training_exercises import (
    get_all_exercises,
    get_exercise,
    get_exercises_by_level,
    get_exercise_count,
    get_curriculum,
)
from core.cinematic_video.flow_operator_training.workflow_simulator import (
    create_initial_state,
    run_exercise_dry_run,
    run_workflow_dry_run,
    run_training_session,
    simulate_partial_run,
)
from core.cinematic_video.flow_operator_training.exercise_validator import (
    validate_exercise_result,
    validate_training_session,
    check_preconditions,
    validate_workflow,
    get_completion_summary,
)
from core.cinematic_video.flow_operator_training.schemas import (
    FlowAction,
    FlowExercise,
    FlowWorkflow,
    DryRunState,
    ExerciseResult,
    TrainingSession,
    SKILL_LEVELS,
)

# ── Phase 5: Flow Sandbox Mode ───────────────────────────────────────────────
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
)
from core.cinematic_video.sandbox.flow_experiment_runner import (
    run_experiment,
    run_batch_experiments,
    get_experiment_history,
)

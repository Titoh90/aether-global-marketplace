#!/usr/bin/env python3
"""
flow_operator_training — Flow Operator Training Layer (PHASE 4).

DRY-RUN ONLY: No video generation. No Flow API calls.
Teaches the agent HOW to use Flow's UI through structured exercises.

24 exercises across 4 skill levels:
    basic         (6)  — Navigation, prompts, aspect ratios, style presets
    intermediate  (6)  — Extend, export, image-to-video, continuity
    advanced      (6)  — Scene builder, ingredients, credit budgets, lighting
    expert        (6)  — 5-shot ads, failure recovery, platform variants

Sub-modules:
    schemas.py              — Frozen dataclasses for exercises + dry-run state
    training_exercises.py   — 24 exercises (basic→expert)
    workflow_simulator.py   — Dry-run state machine (no Flow API)
    exercise_validator.py   — Validates exercise results (non-blocking)

Rules:
    - NO video generation in this layer
    - NO Flow API calls
    - NO pipeline modification
    - NEVER modifies runtime critical path
    - NEVER touches Truth Layer, Revenue Layer, Dispatch Gate
    - Pure knowledge + simulation
    - Never raises — always returns results with warnings
    - All schemas frozen=True
"""

from core.cinematic_video.flow_operator_training.schemas import (
    FlowAction,
    FlowExercise,
    FlowWorkflow,
    DryRunState,
    ExerciseResult,
    TrainingSession,
    SKILL_LEVELS,
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

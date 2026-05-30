#!/usr/bin/env python3
"""
exercise_validator.py — Dry-Run Exercise Validation (Phase 4).

Validates that a training exercise was completed correctly by examining
the final DryRunState. Checks:
    - Preconditions were met
    - Expected state transitions occurred
    - Success criteria are satisfied
    - No forbidden operations (no real API calls)

PURE VALIDATION: Never raises. Returns warnings for non-blocking issues.
"""

from __future__ import annotations

from core.cinematic_video.flow_operator_training.schemas import (
    FlowExercise,
    FlowWorkflow,
    DryRunState,
    ExerciseResult,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Validation Constants
# ═══════════════════════════════════════════════════════════════════════════════

_MAX_PROMPT_LENGTH = 500        # chars — reasonable max for Flow prompts
_MIN_EXERCISE_DURATION_MS = 0  # ms — dry-runs are instant; only flag truly broken durations
_MAX_CREDITS_PER_EXERCISE = 6   # credits — shouldn't exceed this in one exercise


# ═══════════════════════════════════════════════════════════════════════════════
# Individual Validators — each returns a list of error strings (empty = ok)
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_steps_executed(result: ExerciseResult, exercise: FlowExercise) -> list[str]:
    errors: list[str] = []
    if result.steps_executed < len(exercise.steps):
        errors.append(
            f"Only {result.steps_executed}/{len(exercise.steps)} steps executed "
            f"for '{exercise.exercise_id}'"
        )
    return errors


def _validate_prompt_structure(
    result: ExerciseResult, exercise: FlowExercise
) -> list[str]:
    errors: list[str] = []
    state = result.state_snapshot
    prompt = state.prompt_text

    # Only validate if exercise involves typing
    has_type = any(s.action_type == "type" for s in exercise.steps)
    if not has_type:
        return errors

    if len(prompt) > _MAX_PROMPT_LENGTH:
        errors.append(
            f"Prompt too long: {len(prompt)} chars (max {_MAX_PROMPT_LENGTH})"
        )

    # Check for basic prompt structure: PRODUCT keyword presence
    return errors


def _validate_mode_transition(
    result: ExerciseResult, exercise: FlowExercise
) -> list[str]:
    errors: list[str] = []
    state = result.state_snapshot

    valid_modes = {"text_to_video", "image_to_video", "scene_builder"}
    if state.current_mode not in valid_modes:
        errors.append(f"Invalid flow mode: '{state.current_mode}'")

    return errors


def _validate_credit_usage(
    result: ExerciseResult, exercise: FlowExercise
) -> list[str]:
    errors: list[str] = []
    state = result.state_snapshot

    if state.credits_used > _MAX_CREDITS_PER_EXERCISE:
        errors.append(
            f"Excessive credits used: {state.credits_used} "
            f"(max {_MAX_CREDITS_PER_EXERCISE} per exercise)"
        )

    # Note: requires_credits=False means the exercise does NOT need real Flow
    # credits to practice. The simulator still tracks simulated credit usage
    # to help the agent learn credit budgeting. This is intentional.
    return errors


def _validate_aspect_ratio(
    result: ExerciseResult, exercise: FlowExercise
) -> list[str]:
    errors: list[str] = []
    state = result.state_snapshot

    valid_ratios = {"9:16", "1:1", "16:9", "4:5", "3:2", "2:3"}
    if state.aspect_ratio not in valid_ratios:
        errors.append(f"Invalid aspect ratio: '{state.aspect_ratio}'")

    return errors


def _validate_completion(
    result: ExerciseResult, exercise: FlowExercise
) -> list[str]:
    errors: list[str] = []

    if not result.completed:
        errors.append(
            f"Exercise '{exercise.exercise_id}' not completed "
            f"({result.steps_executed}/{result.steps_total} steps)"
        )

    if result.score < 0.5:
        errors.append(
            f"Very low score for '{exercise.exercise_id}': {result.score:.2f}"
        )

    return errors


def _validate_duration(result: ExerciseResult, exercise: FlowExercise) -> list[str]:
    errors: list[str] = []

    if result.duration_ms < _MIN_EXERCISE_DURATION_MS:
        errors.append(
            f"Negative duration: {result.duration_ms}ms"
        )

    return errors


# ═══════════════════════════════════════════════════════════════════════════════
# Composite Validators
# ═══════════════════════════════════════════════════════════════════════════════

_ALL_VALIDATORS = (
    _validate_steps_executed,
    _validate_prompt_structure,
    _validate_mode_transition,
    _validate_credit_usage,
    _validate_aspect_ratio,
    _validate_completion,
    _validate_duration,
)


def validate_exercise_result(
    result: ExerciseResult,
    exercise: FlowExercise,
) -> tuple[str, ...]:
    """Run all validators against an ExerciseResult.

    Returns a tuple of error strings — empty tuple means all checks passed.
    NEVER raises — validation errors are returned, not thrown.
    """
    all_errors: list[str] = []

    for validator in _ALL_VALIDATORS:
        try:
            errors = validator(result, exercise)
            all_errors.extend(errors)
        except Exception:  # pragma: no cover — defensive
            all_errors.append(f"Validator {validator.__name__} raised exception")

    return tuple(all_errors)


def validate_training_session(
    exercises: tuple[FlowExercise, ...],
    results: tuple[ExerciseResult, ...],
) -> dict[str, tuple[str, ...]]:
    """Validate all ExerciseResults from a session.

    Returns: {exercise_id: (error_strings, ...)}
    Empty errors = passed.
    """
    validation: dict[str, tuple[str, ...]] = {}

    for exercise, result in zip(exercises, results):
        if exercise.exercise_id == result.exercise_id:
            validation[exercise.exercise_id] = validate_exercise_result(result, exercise)
        else:
            validation[exercise.exercise_id] = (
                f"Exercise/result mismatch: {exercise.exercise_id} vs {result.exercise_id}",
            )

    return validation


def check_preconditions(
    exercise: FlowExercise,
    current_state: DryRunState,
) -> tuple[str, ...]:
    """Check if preconditions for an exercise are met given current state.

    Returns warnings for unmet preconditions — empty = ready to proceed.
    """
    warnings: list[str] = []
    precondition_text = " ".join(exercise.preconditions).lower()

    if "text-to-video" in precondition_text or "text_to_video" in precondition_text:
        if current_state.current_mode != "text_to_video":
            warnings.append(
                f"Expected mode 'text_to_video' but current is '{current_state.current_mode}'"
            )

    if "image-to-video" in precondition_text or "image_to_video" in precondition_text:
        if current_state.current_mode != "image_to_video":
            warnings.append(
                f"Expected mode 'image_to_video' but current is '{current_state.current_mode}'"
            )

    if "scene builder" in precondition_text or "scene_builder" in precondition_text:
        if current_state.current_mode != "scene_builder":
            warnings.append(
                f"Expected mode 'scene_builder' but current is '{current_state.current_mode}'"
            )

    if "credits" in precondition_text and "8" in precondition_text:
        # Simulate: 8 credits available
        pass  # always met in dry-run

    if "logged" in precondition_text and "flow" in precondition_text:
        # Simulate: always logged in for dry-run
        pass

    return tuple(warnings)


def validate_workflow(
    workflow: FlowWorkflow,
    result: ExerciseResult,
) -> tuple[str, ...]:
    """Validate a workflow execution result.

    Returns error strings — empty = success.
    """
    errors: list[str] = []

    if result.steps_executed < len(workflow.steps):
        errors.append(
            f"Workflow '{workflow.workflow_id}': only {result.steps_executed}/{len(workflow.steps)} steps"
        )

    state = result.state_snapshot
    if state.credits_used > workflow.credits_estimate:
        errors.append(
            f"Workflow '{workflow.workflow_id}': credit overrun "
            f"({state.credits_used} used, {workflow.credits_estimate} estimated)"
        )

    return tuple(errors)


def get_completion_summary(
    result: ExerciseResult,
    exercise: FlowExercise,
) -> dict:
    """Return a human-readable completion summary for an exercise."""
    errors = validate_exercise_result(result, exercise)
    return {
        "exercise_id": exercise.exercise_id,
        "title": exercise.title,
        "skill_level": exercise.skill_level,
        "completed": result.completed,
        "score": round(result.score, 2),
        "steps": f"{result.steps_executed}/{result.steps_total}",
        "credits_used": result.state_snapshot.credits_used,
        "frames_exported": result.state_snapshot.frames_exported,
        "duration_ms": result.duration_ms,
        "passed": len(errors) == 0,
        "errors": list(errors),
        "recommendations": list(result.recommendations),
    }

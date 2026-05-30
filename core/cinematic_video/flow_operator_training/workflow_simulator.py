#!/usr/bin/env python3
"""
workflow_simulator.py — Dry-Run Flow UI State Machine (Phase 4).

Simulates executing training exercises step-by-step WITHOUT making any
Flow API calls or generating videos. Tracks simulated UI state:
    - Which panels are open
    - What mode is active
    - Prompt text, aspect ratio, style preset
    - Credit consumption (simulated)
    - Frame exports, clip extensions, scene builder

PURE KNOWLEDGE: No video generation. No pipeline modification.
"""

from __future__ import annotations

import time
import uuid
from typing import Optional

from core.cinematic_video.flow_operator_training.schemas import (
    FlowAction,
    FlowExercise,
    FlowWorkflow,
    DryRunState,
    ExerciseResult,
    TrainingSession,
    SKILL_LEVELS,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Flow Mode Constants (dry‑run only — never call Flow API)
# ═══════════════════════════════════════════════════════════════════════════════

_FLOW_MODES: frozenset[str] = frozenset({
    "text_to_video",
    "image_to_video",
    "scene_builder",
})

_ASPECT_RATIOS: frozenset[str] = frozenset({
    "9:16", "1:1", "16:9", "4:5", "3:2", "2:3",
})

_MOTION_INTENSITIES: frozenset[str] = frozenset({
    "low", "medium", "high",
})

_STYLE_PRESETS: frozenset[str] = frozenset({
    "cinematic", "realistic", "artistic", "animation", "custom",
})


# ═══════════════════════════════════════════════════════════════════════════════
# Action Handlers — one per FlowAction.action_type
# ═══════════════════════════════════════════════════════════════════════════════

def _handle_navigate(action: FlowAction, state: DryRunState) -> DryRunState:
    """Switch to a new panel or tab."""
    updates: dict = {}
    target = action.target.lower()
    payload = action.ui_element_id.lower()

    if "top_nav" in target:
        if "text_to_video" in payload:
            updates["current_mode"] = "text_to_video"
            updates["current_panel"] = "text_to_video"
        elif "image_to_video" in payload:
            updates["current_mode"] = "image_to_video"
            updates["current_panel"] = "image_to_video"
        elif "scene_builder" in payload:
            updates["current_mode"] = "scene_builder"
            updates["current_panel"] = "scene_builder"

    elif "side_panel" in target:
        updates["current_panel"] = action.ui_element_id
    elif "right_panel" in target:
        updates["current_panel"] = action.ui_element_id
    elif "bottom_panel" in target:
        updates["current_panel"] = action.ui_element_id
    elif "center_panel" in target:
        updates["current_panel"] = action.ui_element_id
    elif "video_preview" in target:
        updates["current_panel"] = "video_preview"

    return DryRunState(
        session_id=state.session_id,
        exercise_id=state.exercise_id,
        current_mode=updates.get("current_mode", state.current_mode),
        current_panel=updates.get("current_panel", state.current_panel),
        prompt_text=state.prompt_text,
        aspect_ratio=state.aspect_ratio,
        motion_intensity=state.motion_intensity,
        style_preset=state.style_preset,
        frames_exported=state.frames_exported,
        clips_extended=state.clips_extended,
        scenes_built=state.scenes_built,
        ingredients_added=state.ingredients_added,
        history_searched=state.history_searched,
        credits_used=state.credits_used,
        step_index=state.step_index,
    )


def _handle_click(action: FlowAction, state: DryRunState) -> DryRunState:
    """Simulate clicking a UI element."""
    payload_lower = action.ui_element_id.lower()
    updates: dict = {}

    if ("generate_button" in payload_lower or "gen_btn" in payload_lower
            or "generate" in payload_lower or "generate" in action.target.lower()):
        updates["credits_used"] = state.credits_used + 1
        updates["scenes_built"] = state.scenes_built + 1
    elif "upload_zone" in payload_lower or "upload_product" in payload_lower or "upload_style" in payload_lower:
        updates["ingredients_added"] = state.ingredients_added + 1
    elif "video_timeline" in payload_lower:
        updates["current_panel"] = "video_preview"

    return DryRunState(
        session_id=state.session_id,
        exercise_id=state.exercise_id,
        current_mode=state.current_mode,
        current_panel=updates.get("current_panel", state.current_panel),
        prompt_text=state.prompt_text,
        aspect_ratio=state.aspect_ratio,
        motion_intensity=state.motion_intensity,
        style_preset=state.style_preset,
        frames_exported=state.frames_exported,
        clips_extended=state.clips_extended,
        scenes_built=updates.get("scenes_built", state.scenes_built),
        ingredients_added=updates.get("ingredients_added", state.ingredients_added),
        history_searched=state.history_searched,
        credits_used=updates.get("credits_used", state.credits_used),
        step_index=state.step_index,
    )


def _handle_type(action: FlowAction, state: DryRunState) -> DryRunState:
    """Simulate typing text into a field."""
    updates: dict = {
        "prompt_text": action.payload if action.payload else state.prompt_text,
    }
    if "scene_" in action.target.lower():
        updates["scenes_built"] = state.scenes_built + 1

    return DryRunState(
        session_id=state.session_id,
        exercise_id=state.exercise_id,
        current_mode=state.current_mode,
        current_panel=state.current_panel,
        prompt_text=updates["prompt_text"],
        aspect_ratio=state.aspect_ratio,
        motion_intensity=state.motion_intensity,
        style_preset=state.style_preset,
        frames_exported=state.frames_exported,
        clips_extended=state.clips_extended,
        scenes_built=updates.get("scenes_built", state.scenes_built),
        ingredients_added=state.ingredients_added,
        history_searched=state.history_searched,
        credits_used=state.credits_used,
        step_index=state.step_index,
    )


def _handle_select(action: FlowAction, state: DryRunState) -> DryRunState:
    """Simulate selecting an option from a dropdown/slider."""
    target = action.target.lower()
    payload = action.payload.lower() if action.payload else ""
    updates: dict = {}

    if "aspect_ratio" in target:
        if payload in _ASPECT_RATIOS:
            updates["aspect_ratio"] = payload
    elif "style_preset" in target:
        if payload in _STYLE_PRESETS:
            updates["style_preset"] = payload
    elif "motion_intensity" in target:
        if payload in _MOTION_INTENSITIES:
            updates["motion_intensity"] = payload
    elif "transition" in target:
        updates["scenes_built"] = state.scenes_built + 1  # transition added = scene work

    return DryRunState(
        session_id=state.session_id,
        exercise_id=state.exercise_id,
        current_mode=state.current_mode,
        current_panel=state.current_panel,
        prompt_text=state.prompt_text,
        aspect_ratio=updates.get("aspect_ratio", state.aspect_ratio),
        motion_intensity=updates.get("motion_intensity", state.motion_intensity),
        style_preset=updates.get("style_preset", state.style_preset),
        frames_exported=state.frames_exported,
        clips_extended=state.clips_extended,
        scenes_built=updates.get("scenes_built", state.scenes_built),
        ingredients_added=state.ingredients_added,
        history_searched=state.history_searched,
        credits_used=state.credits_used,
        step_index=state.step_index,
    )


def _handle_export(action: FlowAction, state: DryRunState) -> DryRunState:
    """Simulate exporting a frame."""
    return DryRunState(
        session_id=state.session_id,
        exercise_id=state.exercise_id,
        current_mode=state.current_mode,
        current_panel=state.current_panel,
        prompt_text=state.prompt_text,
        aspect_ratio=state.aspect_ratio,
        motion_intensity=state.motion_intensity,
        style_preset=state.style_preset,
        frames_exported=state.frames_exported + 1,
        clips_extended=state.clips_extended,
        scenes_built=state.scenes_built,
        ingredients_added=state.ingredients_added,
        history_searched=state.history_searched,
        credits_used=state.credits_used,
        step_index=state.step_index,
    )


def _handle_extend(action: FlowAction, state: DryRunState) -> DryRunState:
    """Simulate extending a clip (costs 1 credit)."""
    return DryRunState(
        session_id=state.session_id,
        exercise_id=state.exercise_id,
        current_mode=state.current_mode,
        current_panel=state.current_panel,
        prompt_text=state.prompt_text,
        aspect_ratio=state.aspect_ratio,
        motion_intensity=state.motion_intensity,
        style_preset=state.style_preset,
        frames_exported=state.frames_exported,
        clips_extended=state.clips_extended + 1,
        scenes_built=state.scenes_built,
        ingredients_added=state.ingredients_added,
        history_searched=state.history_searched,
        credits_used=state.credits_used + 1,
        step_index=state.step_index,
    )


def _handle_download(action: FlowAction, state: DryRunState) -> DryRunState:
    """Simulate downloading a generated file — no state change beyond panel."""
    return DryRunState(
        session_id=state.session_id,
        exercise_id=state.exercise_id,
        current_mode=state.current_mode,
        current_panel="video_preview",
        prompt_text=state.prompt_text,
        aspect_ratio=state.aspect_ratio,
        motion_intensity=state.motion_intensity,
        style_preset=state.style_preset,
        frames_exported=state.frames_exported,
        clips_extended=state.clips_extended,
        scenes_built=state.scenes_built,
        ingredients_added=state.ingredients_added,
        history_searched=state.history_searched,
        credits_used=state.credits_used,
        step_index=state.step_index,
    )


_ACTION_HANDLERS = {
    "navigate": _handle_navigate,
    "click":     _handle_click,
    "type":      _handle_type,
    "select":    _handle_select,
    "export":    _handle_export,
    "extend":    _handle_extend,
    "download":  _handle_download,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Step Sequencer
# ═══════════════════════════════════════════════════════════════════════════════

def _apply_step(action: FlowAction, state: DryRunState) -> DryRunState:
    """Apply a single FlowAction to the current state."""
    handler = _ACTION_HANDLERS.get(action.action_type)
    if handler is None:
        # Unknown action type — return state unchanged (never raise)
        return DryRunState(
            session_id=state.session_id,
            exercise_id=state.exercise_id,
            current_mode=state.current_mode,
            current_panel=state.current_panel,
            prompt_text=state.prompt_text,
            aspect_ratio=state.aspect_ratio,
            motion_intensity=state.motion_intensity,
            style_preset=state.style_preset,
            frames_exported=state.frames_exported,
            clips_extended=state.clips_extended,
            scenes_built=state.scenes_built,
            ingredients_added=state.ingredients_added,
            history_searched=state.history_searched,
            credits_used=state.credits_used,
            step_index=state.step_index + 1,
        )
    next_state = handler(action, state)
    return DryRunState(
        session_id=next_state.session_id,
        exercise_id=next_state.exercise_id,
        current_mode=next_state.current_mode,
        current_panel=next_state.current_panel,
        prompt_text=next_state.prompt_text,
        aspect_ratio=next_state.aspect_ratio,
        motion_intensity=next_state.motion_intensity,
        style_preset=next_state.style_preset,
        frames_exported=next_state.frames_exported,
        clips_extended=next_state.clips_extended,
        scenes_built=next_state.scenes_built,
        ingredients_added=next_state.ingredients_added,
        history_searched=next_state.history_searched,
        credits_used=next_state.credits_used,
        step_index=state.step_index + 1,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def create_initial_state(exercise_id: str, session_id: str | None = None) -> DryRunState:
    """Create a fresh DryRunState for starting an exercise."""
    return DryRunState(
        session_id=session_id or f"session_{uuid.uuid4().hex[:12]}",
        exercise_id=exercise_id,
    )


def run_exercise_dry_run(
    exercise: FlowExercise,
    session_id: str | None = None,
    starting_state: DryRunState | None = None,
) -> ExerciseResult:
    """Run ALL steps of an exercise through the dry-run simulator.

    Returns an ExerciseResult — NEVER raises.
    Each step mutates the DryRunState according to its action_type.
    """
    t_start = time.monotonic()

    state = starting_state if starting_state is not None else create_initial_state(
        exercise.exercise_id, session_id
    )

    steps_executed = 0
    validation_errors: list[str] = []
    recommendations: list[str] = []

    try:
        for i, step in enumerate(exercise.steps):
            state = _apply_step(step, state)
            steps_executed += 1

        duration_ms = int((time.monotonic() - t_start) * 1000)
        completed = steps_executed == len(exercise.steps)

        if not completed:
            validation_errors.append(
                f"Only {steps_executed}/{len(exercise.steps)} steps executed"
            )
    except Exception as exc:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        completed = False
        validation_errors.append(f"Simulation error: {exc}")

    # Score: proportion of steps completed
    score = steps_executed / max(len(exercise.steps), 1)

    if score < 1.0:
        recommendations.append(f"Re-run exercise '{exercise.exercise_id}' to complete all steps")

    # Add skill-based recommendations
    level_order = ["basic", "intermediate", "advanced", "expert"]
    if exercise.skill_level in level_order:
        idx = level_order.index(exercise.skill_level)
        if idx < len(level_order) - 1 and score >= 0.8:
            recommendations.append(f"Ready for {level_order[idx + 1]} level exercises")

    if exercise.skill_level == "expert" and score >= 0.9:
        recommendations.append("All expert exercises completed — you are a Flow Director")

    return ExerciseResult(
        exercise_id=exercise.exercise_id,
        completed=completed,
        steps_executed=steps_executed,
        steps_total=len(exercise.steps),
        state_snapshot=state,
        validation_errors=tuple(validation_errors),
        score=score,
        duration_ms=duration_ms,
        recommendations=tuple(recommendations),
    )


def run_workflow_dry_run(
    workflow: FlowWorkflow,
    session_id: str | None = None,
) -> ExerciseResult:
    """Run a FlowWorkflow through dry-run simulation.

    Workflows are treated as exercises with a synthetic exercise_id.
    """
    exercise = FlowExercise(
        exercise_id=f"workflow_{workflow.workflow_id}",
        title=workflow.name,
        skill_level=workflow.skill_level,
        goal=workflow.description,
        description=workflow.description,
        preconditions=(),
        steps=workflow.steps,
        expected_outcome="Workflow completed.",
        success_criteria=("All steps executed",),
        tips=(),
        common_mistakes=(),
    )
    return run_exercise_dry_run(exercise, session_id=session_id)


def run_training_session(
    exercises: tuple[FlowExercise, ...],
    session_id: str | None = None,
) -> TrainingSession:
    """Run a batch of exercises and return a TrainingSession summary.

    Exercises run sequentially — state is NOT carried between exercises.
    Each exercise starts fresh with its own DryRunState.
    """
    sid = session_id or f"session_{uuid.uuid4().hex[:12]}"
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results: list[ExerciseResult] = []
    skill_progress: dict[str, float] = {}

    for exercise in exercises:
        result = run_exercise_dry_run(exercise, session_id=sid)
        results.append(result)

    passed = sum(1 for r in results if r.completed)
    total_score = sum(r.score for r in results) / max(len(results), 1)

    # Compute per-skill-level mastery
    for level in SKILL_LEVELS:
        level_results = [r for r in results
                         if any(e.exercise_id == r.exercise_id and e.skill_level == level
                                for e in exercises)]
        if level_results:
            skill_progress[level] = sum(r.score for r in level_results) / len(level_results)
        else:
            skill_progress[level] = 0.0

    # Next recommendation based on lowest incomplete skill level
    next_rec = "basic"
    for level in ("basic", "intermediate", "advanced", "expert"):
        if skill_progress.get(level, 0.0) < 0.8:
            next_rec = level
            break

    return TrainingSession(
        session_id=sid,
        started_at=started_at,
        exercises_run=tuple(results),
        total_score=total_score,
        exercises_passed=passed,
        exercises_total=len(exercises),
        next_recommended=next_rec,
        skill_progress=skill_progress,
    )


def simulate_partial_run(
    exercise: FlowExercise,
    stop_at_step: int = 3,
    session_id: str | None = None,
) -> ExerciseResult:
    """Simulate an exercise but stop early (e.g., at step 3 of 6).

    Useful for testing interruption/resume scenarios.
    """
    state = create_initial_state(exercise.exercise_id, session_id)
    steps_to_run = min(stop_at_step, len(exercise.steps))
    steps_executed = 0

    for i in range(steps_to_run):
        state = _apply_step(exercise.steps[i], state)
        steps_executed += 1

    return ExerciseResult(
        exercise_id=exercise.exercise_id,
        completed=False,
        steps_executed=steps_executed,
        steps_total=len(exercise.steps),
        state_snapshot=state,
        validation_errors=("Exercise interrupted at step %d" % steps_to_run,),
        score=steps_executed / max(len(exercise.steps), 1),
        duration_ms=0,
        recommendations=("Resume from step %d" % (steps_to_run + 1),),
    )

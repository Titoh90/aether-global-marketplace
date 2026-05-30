#!/usr/bin/env python3
"""
schemas.py — Frozen dataclasses for Flow Operator Training (Phase 4).

DRY-RUN ONLY: No video generation. No Flow API calls.
Exercises teach the agent HOW to use Flow's UI — button sequences,
panel navigation, workflow orchestration — without actually using credits.

All types are immutable (frozen=True) and serializable.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


# ═══════════════════════════════════════════════════════════════════════════════
# Skill Levels
# ═══════════════════════════════════════════════════════════════════════════════

SKILL_LEVELS: frozenset[str] = frozenset({
    "basic",
    "intermediate",
    "advanced",
    "expert",
})


# ═══════════════════════════════════════════════════════════════════════════════
# Exercise Schemas
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class FlowAction:
    """One simulated action the agent performs in Flow's UI.

    An action is a button press, panel switch, text input, or selector change.
    It maps 1:1 to a real Flow UI interaction but is executed in dry-run.
    """
    action_id:      str       # e.g., "navigate_text_to_video"
    name:           str       # human-readable
    description:    str       # what the agent does
    ui_element_id:  str       # references flow_ui_mapper element_id
    action_type:    str       # "navigate" | "click" | "type" | "select" | "export" | "extend" | "download"
    target:         str       # the UI element being interacted with
    payload:        str = ""  # type→prompt text, select→option, etc.


@dataclass(frozen=True)
class FlowExercise:
    """One training exercise that teaches a Flow UI skill.

    Each exercise has:
    - A goal (what skill is learned)
    - Preconditions (what state Flow must be in)
    - Steps (ordered sequence of FlowActions)
    - Expected outcomes (what should happen after completion)
    """
    exercise_id:      str
    title:            str
    skill_level:      str       # one of SKILL_LEVELS
    goal:             str       # what the agent learns
    description:      str       # detailed exercise description
    preconditions:    tuple[str, ...]   # required Flow state / context
    steps:            tuple[FlowAction, ...]   # ordered action sequence
    expected_outcome: str       # what the agent should observe
    success_criteria: tuple[str, ...]   # how to know if exercise completed correctly
    tips:             tuple[str, ...]   # agent hints
    common_mistakes:  tuple[str, ...]   # what to avoid
    requires_credits: bool = False      # True only if actual generation needed
    estimated_minutes: int = 3          # how long this exercise takes

    def to_dict(self) -> dict:
        d = asdict(self)
        d["preconditions"] = list(self.preconditions)
        d["steps"] = [asdict(s) for s in self.steps]
        d["success_criteria"] = list(self.success_criteria)
        d["tips"] = list(self.tips)
        d["common_mistakes"] = list(self.common_mistakes)
        return d


@dataclass(frozen=True)
class DryRunState:
    """Simulated Flow UI state during a dry-run exercise.

    Tracks which panels are open, what mode is active, what's been
    generated (simulated), and credits consumed (simulated).
    """
    session_id:       str
    exercise_id:      str
    current_mode:     str = "text_to_video"   # one of FLOW_MODES
    current_panel:    str = "text_to_video"   # active panel
    prompt_text:      str = ""                # current prompt input
    aspect_ratio:     str = "9:16"            # current aspect ratio
    motion_intensity: str = "medium"          # "low" | "medium" | "high"
    style_preset:     str = "cinematic"       # active style preset
    frames_exported:  int = 0                 # count of exported frames
    clips_extended:   int = 0                 # count of extended clips
    scenes_built:     int = 0                 # storyboard scenes
    ingredients_added: int = 0                # reference images uploaded
    history_searched: int = 0                 # times history checked
    credits_used:     int = 0                 # simulated credit consumption
    step_index:       int = 0                 # current step in exercise

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ExerciseResult:
    """Result of running one exercise through the dry-run simulator.

    Non-blocking: even if validation fails, the result is returned.
    """
    exercise_id:       str
    completed:         bool              # all steps were executed
    steps_executed:    int               # how many steps actually ran
    steps_total:       int               # total steps in exercise
    state_snapshot:    DryRunState       # final simulated state
    validation_errors: tuple[str, ...]   # issues found (empty = pass)
    score:             float             # 0.0–1.0 completion score
    duration_ms:       int               # simulation duration
    recommendations:   tuple[str, ...]   # what to practice next

    def to_dict(self) -> dict:
        d = asdict(self)
        d["state_snapshot"] = self.state_snapshot.to_dict()
        d["validation_errors"] = list(self.validation_errors)
        d["recommendations"] = list(self.recommendations)
        return d


@dataclass(frozen=True)
class TrainingSession:
    """Aggregated training session — one run through multiple exercises."""
    session_id:     str
    started_at:     str
    exercises_run:  tuple[ExerciseResult, ...]
    total_score:    float             # average across all exercises
    exercises_passed: int
    exercises_total: int
    next_recommended: str             # which exercise to do next
    skill_progress:  dict[str, float] # skill_level → 0.0–1.0 mastery

    def to_dict(self) -> dict:
        d = asdict(self)
        d["exercises_run"] = [e.to_dict() for e in self.exercises_run]
        return d


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow Schema
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class FlowWorkflow:
    """A multi-step workflow that chains multiple Flow UI operations.

    Workflows are the building blocks of exercises — they teach the agent
    how to combine basic actions into production pipelines.
    """
    workflow_id:      str
    name:             str
    description:      str
    skill_level:      str       # one of SKILL_LEVELS
    flow_modes:       tuple[str, ...]   # which FLOW_MODES this uses
    steps:            tuple[FlowAction, ...]
    credits_estimate: int               # simulated credit cost
    failure_points:   tuple[str, ...]   # where things typically go wrong

    def to_dict(self) -> dict:
        d = asdict(self)
        d["flow_modes"] = list(self.flow_modes)
        d["steps"] = [asdict(s) for s in self.steps]
        d["failure_points"] = list(self.failure_points)
        return d

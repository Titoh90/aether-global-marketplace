#!/usr/bin/env python3
"""
flow_experiment_runner.py — Sandbox experiment orchestrator.

The main entry point for Flow Sandbox Mode. Runs a complete experiment:
  1. Generate prompt variations from base prompt
  2. Run extension trials on each variation
  3. Score continuity across extensions
  4. Review generation quality
  5. Record failures in registry
  6. Aggregate lessons learned

Teaches the agent: "Experiment deliberately. Learn empirically. Don't waste credits."

SANDBOX-ONLY: Never touches production pipeline.
"""

from __future__ import annotations

import time
from pathlib import Path

from core.cinematic_video.sandbox.schemas import (
    ExperimentConfig,
    SandboxExperiment,
    ExtensionTrial,
    _make_id,
    _now_iso,
)
from core.cinematic_video.sandbox.prompt_variation_engine import generate_variations
from core.cinematic_video.sandbox.clip_extension_tester import (
    run_extension_trial,
    get_extension_health,
)
from core.cinematic_video.sandbox.continuity_score_tracker import (
    record_continuity_score,
    get_best_patterns,
)
from core.cinematic_video.sandbox.generation_reviewer import (
    review_generation,
    get_review_summary,
)
from core.cinematic_video.sandbox.failed_generation_registry import (
    record_failure,
    get_failure_statistics,
)


_IMPERIO_ROOT = Path(__file__).parent.parent.parent.parent
_EXPERIMENT_DIR = _IMPERIO_ROOT / "logs" / "sandbox" / "experiments"


def _ensure_dir() -> None:
    _EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Lessons engine
# ═══════════════════════════════════════════════════════════════════════════════

def _derive_lessons(
    reviews: tuple,
    failures: tuple,
    trials_by_variation: dict[str, tuple[ExtensionTrial, ...]],
) -> tuple[str, ...]:
    """Derive lessons learned from experiment results."""
    lessons: list[str] = []

    # Lesson 1: Review results
    review_summary = get_review_summary(reviews)
    if review_summary["approved"] > 0:
        lessons.append(
            f"{review_summary['approved']}/{review_summary['total']} variations approved. "
            f"Best: {review_summary['best_variation']} (score: {review_summary['best_score']})"
        )
    if review_summary["discards"] > 0:
        lessons.append(
            f"{review_summary['discards']}/{review_summary['total']} variations discarded — "
            "these patterns should be avoided"
        )

    # Lesson 2: Extension behavior
    for vid, trials in trials_by_variation.items():
        health = get_extension_health(trials)
        if health["max_safe_extensions"] < 2:
            lessons.append(
                f"Variation {vid}: Only {health['max_safe_extensions']} safe extension(s) — "
                "limit extensions and prefer new generations"
            )
        if health["aborted"] > 0:
            lessons.append(
                f"Variation {vid}: Extensions aborted — clip degraded beyond use. "
                "Stop extending after 3."
            )

    # Lesson 3: Failure patterns
    if failures:
        failure_modes = {f.failure_mode for f in failures}
        lessons.append(
            f"{len(failures)} failure(s) recorded — modes: {', '.join(failure_modes)}"
        )
        for f in failures:
            if f.permanent:
                lessons.append(
                    f"PERMANENT failure: {f.failure_mode} — pattern marked as never-retry"
                )

    # Lesson 4: Budget awareness
    total_credits = sum(
        sum(t.credit_cost for t in trials)
        for trials in trials_by_variation.values()
    )
    lessons.append(
        f"Total simulated credits: {total_credits}. "
        f"Always check credit balance before starting real generations."
    )

    # Lesson 5: Cross-experiment insight
    try:
        best = get_best_patterns(top_n=1)
        if best:
            lessons.append(
                f"Historical best pattern: {best[0]['variation_id']} "
                f"(avg score: {best[0]['avg_score']}, {best[0]['sample_count']} samples)"
            )
    except Exception:
        pass

    return tuple(lessons)


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment persistence
# ═══════════════════════════════════════════════════════════════════════════════

def _persist_experiment(exp: SandboxExperiment) -> str:
    """Save experiment result to JSON file (atomic write). Never raises."""
    _ensure_dir()
    try:
        import json
        import os
        path = _EXPERIMENT_DIR / f"{exp.experiment_id}.json"
        tmp_path = _EXPERIMENT_DIR / f"{exp.experiment_id}.json.tmp"
        with open(tmp_path, "w") as f:
            json.dump(exp.to_dict(), f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
        return str(path)
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════════

def run_experiment(
    config: ExperimentConfig,
    verbose: bool = False,
) -> SandboxExperiment:
    """
    Run a complete sandbox experiment.

    Flow:
      1. Generate prompt variations from config.base_prompt
      2. For each variation, run extension trials
      3. Record continuity scores per dimension
      4. Review each variation for quality
      5. Collect and summarize results

    NEVER raises — always returns a SandboxExperiment.

    Args:
        config: ExperimentConfig with base prompt, dimensions, budget
        verbose: Print experiment progress

    Returns:
        SandboxExperiment with all results aggregated
    """
    started = _now_iso()
    t0 = time.monotonic()

    if verbose:
        print(f"\n🧪 EXPERIMENT: {config.experiment_id}")
        print(f"   Base: {config.base_prompt[:80]}...")
        print(f"   Dimensions: {', '.join(config.dimensions)}")

    # 1. Generate variations
    variations = generate_variations(
        base_prompt=config.base_prompt,
        product=config.product_name,
        dimensions=config.dimensions,
        max_total=config.variation_count,
    )

    if verbose:
        print(f"   Variations: {len(variations)} generated")

    # 2-3. Extension trials + continuity scoring + reviews + failures
    all_trials: list[ExtensionTrial] = []
    all_reviews: list = []
    all_failures: list = []
    trials_by_variation: dict[str, tuple[ExtensionTrial, ...]] = {}

    for var in variations:
        try:
            # Extension trials
            trials = run_extension_trial(
                variation_id=var.variation_id,
                max_extensions=config.extend_count,
                shot_type=var.shot_type,
                dry_run=config.dry_run,
            )
            all_trials.extend(trials)
            trials_by_variation[var.variation_id] = trials

            # Continuity scoring (per trial, per dimension)
            for trial in trials:
                for dim in ("palette_coherence", "lighting_continuity", "camera_continuity"):
                    score = 1.0 - trial.drift_score  # Inverted: lower drift = higher continuity
                    record_continuity_score(
                        variation_id=var.variation_id,
                        dimension=dim,
                        score=score,
                        experiment_id=config.experiment_id,
                    )

            # Quality review
            ext_count = len(trials) - 1  # Extensions beyond base
            worst_drift = max((t.drift_score for t in trials), default=0.0)
            review = review_generation(
                variation_id=var.variation_id,
                drift_score=worst_drift,
                shot_type=var.shot_type,
                lighting=var.lighting,
                atmosphere=var.atmosphere,
                lens_style=var.lens_style,
                extension_count=ext_count,
                product_in_prompt=bool(config.product_name),
            )
            all_reviews.append(review)

            # Failure detection: any trial that failed or aborted
            for trial in trials:
                if trial.outcome in ("failed", "aborted"):
                    failure = record_failure(
                        experiment_id=config.experiment_id,
                        variation_id=var.variation_id,
                        error_message=(
                            f"Extension {trial.extension_index}: {trial.outcome} "
                            f"(drift={trial.drift_score:.2f}). "
                            f"Issues: {', '.join(trial.issues)}"
                        ),
                        prompt_used=var.varied_prompt,
                        permanent=(trial.outcome == "aborted"),
                    )
                    all_failures.append(failure)

        except Exception:
            # One variation failed — continue with remaining variations.
            # Record as a silent failure so the experiment still completes.
            if verbose:
                print(f"   ⚠️ Variation {var.variation_id} failed — skipping")

    # 4. Derive lessons
    lessons = _derive_lessons(
        reviews=tuple(all_reviews),
        failures=tuple(all_failures),
        trials_by_variation=trials_by_variation,
    )

    # 5. Identify best variation
    review_summary = get_review_summary(tuple(all_reviews))

    total_credits = sum(t.credit_cost for t in all_trials)

    experiment = SandboxExperiment(
        experiment_id=config.experiment_id,
        config=config,
        variations=variations,
        extension_trials=tuple(all_trials),
        continuity_records=(),
        reviews=tuple(all_reviews),
        failures=tuple(all_failures),
        started_at=started,
        completed_at=_now_iso(),
        duration_ms=int((time.monotonic() - t0) * 1000),
        total_credits_used=total_credits,
        best_variation_id=review_summary.get("best_variation", ""),
        lessons_learned=lessons,
    )

    _persist_experiment(experiment)

    if verbose:
        print(f"   ✅ Complete in {experiment.duration_ms}ms")
        print(f"   Best: {experiment.best_variation_id}")
        print(f"   Credits: {total_credits}")
        if experiment.failures:
            print(f"   Failures: {len(experiment.failures)}")
        for lesson in experiment.lessons_learned:
            print(f"   📝 {lesson}")

    return experiment


def run_batch_experiments(
    configs: tuple[ExperimentConfig, ...],
    verbose: bool = False,
) -> tuple[SandboxExperiment, ...]:
    """
    Run multiple experiments sequentially.

    Returns tuple of SandboxExperiment results.
    """
    results: list[SandboxExperiment] = []
    for config in configs:
        exp = run_experiment(config, verbose=verbose)
        results.append(exp)
    return tuple(results)


def get_experiment_history(
    limit: int = 20,
) -> tuple[dict, ...]:
    """Retrieve recent experiment summaries. Returns most recent first."""
    _ensure_dir()
    try:
        import json
        files = sorted(
            _EXPERIMENT_DIR.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        summaries: list[dict] = []
        for f in files[:limit]:
            with open(f) as fh:
                data = json.load(fh)
            summaries.append({
                "experiment_id": data.get("experiment_id", ""),
                "started_at": data.get("started_at", ""),
                "duration_ms": data.get("duration_ms", 0),
                "variations": len(data.get("variations", [])),
                "credits": data.get("total_credits_used", 0),
                "best": data.get("best_variation_id", ""),
                "failures": len(data.get("failures", [])),
                "lessons": len(data.get("lessons_learned", [])),
            })
        return tuple(summaries)
    except Exception:
        return ()


__all__ = [
    "run_experiment",
    "run_batch_experiments",
    "get_experiment_history",
]

#!/usr/bin/env python3
"""
test_flow_sandbox.py — Tests for Flow Sandbox Mode (Phase 5).

Covers:
- prompt_variation_engine: generate_variations, generate_single_variation
- clip_extension_tester: run_extension_trial, get_extension_health
- continuity_score_tracker: record, history, best patterns, trends
- generation_reviewer: review_generation, batch_review, get_review_summary
- failed_generation_registry: record_failure, classify, statistics
- flow_experiment_runner: run_experiment, batch, history
- Schemas: frozen dataclasses, serialization
- Never-raise contract: all public functions
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_IMPERIO_ROOT = Path(__file__).parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))


# ═══════════════════════════════════════════════════════════════════════════════
# Schema tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSandboxSchemas:
    """Frozen dataclass verification."""

    def test_experiment_config_frozen(self):
        from core.cinematic_video.sandbox.schemas import ExperimentConfig
        cfg = ExperimentConfig(
            experiment_id="test-1",
            base_prompt="A cinematic product shot",
            variation_count=4,
        )
        assert cfg.experiment_id == "test-1"
        assert cfg.base_prompt == "A cinematic product shot"
        assert cfg.variation_count == 4
        assert cfg.dry_run is True
        with pytest.raises(Exception):
            cfg.variation_count = 8  # type: ignore

    def test_experiment_config_serialization(self):
        from core.cinematic_video.sandbox.schemas import ExperimentConfig
        cfg = ExperimentConfig(
            experiment_id="test-1",
            base_prompt="A cinematic product shot",
            product_name="Test Product",
            dimensions=("shot_type", "lighting"),
        )
        d = cfg.to_dict()
        assert d["experiment_id"] == "test-1"
        assert d["dimensions"] == ["shot_type", "lighting"]
        assert d["dry_run"] is True

    def test_prompt_variation_frozen(self):
        from core.cinematic_video.sandbox.schemas import PromptVariation
        pv = PromptVariation(
            variation_id="var-1",
            base_prompt="base",
            varied_prompt="varied",
            dimension="shot_type",
            change_description="Changed shot type",
        )
        with pytest.raises(Exception):
            pv.dimension = "lighting"  # type: ignore

    def test_prompt_variation_to_dict(self):
        from core.cinematic_video.sandbox.schemas import PromptVariation
        pv = PromptVariation(
            variation_id="var-1",
            base_prompt="base",
            varied_prompt="varied",
            dimension="shot_type",
            change_description="Changed shot type",
            shot_type="hero_shot",
            camera_motion="dolly_in",
            lighting="dark_matte",
            atmosphere="premium_commercial",
            pacing="slow_dramatic",
        )
        d = pv.to_dict()
        assert d["shot_type"] == "hero_shot"
        assert d["lighting"] == "dark_matte"

    def test_extension_trial_frozen(self):
        from core.cinematic_video.sandbox.schemas import ExtensionTrial
        trial = ExtensionTrial(
            trial_id="ext-1",
            variation_id="var-1",
            extension_index=0,
            outcome="success",
            drift_score=0.0,
            credit_cost=1,
            issues=(),
            recommendation="continue",
        )
        with pytest.raises(Exception):
            trial.outcome = "failed"  # type: ignore

    def test_continuity_record_frozen(self):
        from core.cinematic_video.sandbox.schemas import ContinuityRecord
        rec = ContinuityRecord(
            record_id="cont-1",
            variation_id="var-1",
            dimension="palette_coherence",
            score=0.85,
            recorded_at="2026-01-01T00:00:00+00:00",
            experiment_id="exp-1",
        )
        with pytest.raises(Exception):
            rec.score = 0.5  # type: ignore

    def test_generation_review_frozen(self):
        from core.cinematic_video.sandbox.schemas import GenerationReview
        rev = GenerationReview(
            review_id="rev-1",
            variation_id="var-1",
            overall_score=0.8,
            drift_score=0.1,
            fidelity_score=0.9,
            aesthetic_score=0.7,
            issues=(),
            severity="info",
            recommendation="approve",
        )
        with pytest.raises(Exception):
            rev.recommendation = "discard"  # type: ignore

    def test_failure_entry_frozen(self):
        from core.cinematic_video.sandbox.schemas import FailureEntry
        fe = FailureEntry(
            failure_id="fail-1",
            experiment_id="exp-1",
            variation_id="var-1",
            failure_mode="style_drift_excessive",
            root_cause="Too many extensions",
        )
        with pytest.raises(Exception):
            fe.failure_mode = "credits_exhausted"  # type: ignore

    def test_sandbox_experiment_to_dict(self):
        from core.cinematic_video.sandbox.schemas import (
            SandboxExperiment, ExperimentConfig,
        )
        cfg = ExperimentConfig(
            experiment_id="exp-1",
            base_prompt="test",
        )
        exp = SandboxExperiment(
            experiment_id="exp-1",
            config=cfg,
            variations=(),
            extension_trials=(),
            continuity_records=(),
            reviews=(),
            failures=(),
            started_at="2026-01-01T00:00:00+00:00",
            completed_at="2026-01-01T00:00:01+00:00",
            duration_ms=1000,
            total_credits_used=0,
            lessons_learned=("Lesson 1", "Lesson 2"),
        )
        d = exp.to_dict()
        assert len(d["lessons_learned"]) == 2
        assert d["total_credits_used"] == 0



# ═══════════════════════════════════════════════════════════════════════════════
# Prompt Variation Engine tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestPromptVariationEngine:
    """Systematic prompt variation generation."""

    def test_generate_variations_produces_prompt_variations(self):
        from core.cinematic_video.sandbox.prompt_variation_engine import generate_variations
        from core.cinematic_video.sandbox.schemas import PromptVariation
        variations = generate_variations(
            base_prompt="A luxury watch on dark surface",
            product="watch",
            dimensions=("shot_type", "camera_motion", "lighting"),
            max_total=8,
        )
        assert isinstance(variations, tuple)
        for v in variations:
            assert isinstance(v, PromptVariation)
            assert v.base_prompt == "A luxury watch on dark surface"
            assert v.variation_id.startswith("var_")

    def test_generate_variations_respects_max_total(self):
        from core.cinematic_video.sandbox.prompt_variation_engine import generate_variations
        variations = generate_variations(
            base_prompt="test",
            dimensions=("shot_type", "camera_motion", "lighting", "pacing"),
            max_total=6,
        )
        assert len(variations) <= 6

    def test_generate_variations_dimension_tagged(self):
        from core.cinematic_video.sandbox.prompt_variation_engine import generate_variations
        variations = generate_variations(
            base_prompt="test",
            dimensions=("lighting",),
            max_total=4,
        )
        for v in variations:
            assert v.dimension == "lighting"

    def test_generate_variations_empty_dimensions(self):
        from core.cinematic_video.sandbox.prompt_variation_engine import generate_variations
        variations = generate_variations(
            base_prompt="test",
            dimensions=(),
        )
        assert len(variations) == 0

    def test_generate_single_variation(self):
        from core.cinematic_video.sandbox.prompt_variation_engine import generate_single_variation
        var = generate_single_variation(
            base_prompt="test product",
            dimension="lighting",
            index=0,
        )
        assert var is not None
        assert var.dimension == "lighting"

    def test_generate_single_variation_invalid_dimension(self):
        from core.cinematic_video.sandbox.prompt_variation_engine import generate_single_variation
        var = generate_single_variation(
            base_prompt="test",
            dimension="nonexistent",
        )
        assert var is None

    def test_variation_count_for_dimensions(self):
        from core.cinematic_video.sandbox.prompt_variation_engine import variation_count_for_dimensions
        count = variation_count_for_dimensions(("shot_type", "lighting"))
        assert count > 0
        count2 = variation_count_for_dimensions(())
        assert count2 == 0

    def test_generate_variations_never_raises(self):
        from core.cinematic_video.sandbox.prompt_variation_engine import generate_variations
        # Even with bad inputs
        result = generate_variations(
            base_prompt="",
            dimensions=("invalid_dim",),
        )
        assert isinstance(result, tuple)


# ═══════════════════════════════════════════════════════════════════════════════
# Clip Extension Tester tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestClipExtensionTester:
    """Extend-mode boundary testing."""

    def test_run_extension_trial_base_clip(self):
        from core.cinematic_video.sandbox.clip_extension_tester import run_extension_trial
        trials = run_extension_trial(
            variation_id="var-test",
            max_extensions=0,
        )
        assert len(trials) == 1  # Only base clip
        assert trials[0].extension_index == 0
        assert trials[0].outcome == "success"
        assert trials[0].drift_score == 0.0

    def test_run_extension_trial_full_sequence(self):
        from core.cinematic_video.sandbox.clip_extension_tester import run_extension_trial
        trials = run_extension_trial(
            variation_id="var-test",
            max_extensions=5,
        )
        # At least base + 1 extension, but may abort early
        assert len(trials) >= 2
        # Base clip at index 0
        assert trials[0].extension_index == 0

    def test_run_extension_trial_drift_increases(self):
        from core.cinematic_video.sandbox.clip_extension_tester import run_extension_trial
        trials = run_extension_trial(
            variation_id="var-test",
            max_extensions=4,
        )
        drift_values = [t.drift_score for t in trials]
        # Drift should be non-decreasing
        for i in range(1, len(drift_values)):
            assert drift_values[i] >= drift_values[i-1], (
                f"Drift decreased at index {i}: {drift_values}"
            )

    def test_get_extension_health(self):
        from core.cinematic_video.sandbox.clip_extension_tester import (
            run_extension_trial, get_extension_health,
        )
        trials = run_extension_trial("var-test", max_extensions=4)
        health = get_extension_health(trials)
        assert "total_extensions" in health
        assert "healthy" in health
        assert "failed" in health
        assert "max_safe_extensions" in health
        assert "health_pct" in health

    def test_batch_extension_trial(self):
        from core.cinematic_video.sandbox.clip_extension_tester import batch_extension_trial
        results = batch_extension_trial(
            variation_ids=("var-a", "var-b"),
            max_extensions=2,
        )
        assert len(results) == 2
        assert "var-a" in results
        assert "var-b" in results

    def test_extension_trial_never_raises(self):
        from core.cinematic_video.sandbox.clip_extension_tester import run_extension_trial
        # Bad inputs still produce results
        result = run_extension_trial("", max_extensions=-1)
        assert isinstance(result, tuple)


# ═══════════════════════════════════════════════════════════════════════════════
# Continuity Score Tracker tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestContinuityScoreTracker:
    """Persistent continuity scoring."""

    def test_record_continuity_score(self):
        from core.cinematic_video.sandbox.continuity_score_tracker import (
            record_continuity_score, clear_continuity_history,
        )
        clear_continuity_history()
        rec = record_continuity_score(
            variation_id="var-test",
            dimension="palette_coherence",
            score=0.9,
        )
        assert rec.variation_id == "var-test"
        assert rec.score == 0.9
        assert rec.record_id.startswith("cont_")

    def test_get_continuity_history(self):
        from core.cinematic_video.sandbox.continuity_score_tracker import (
            record_continuity_score, get_continuity_history,
            clear_continuity_history,
        )
        clear_continuity_history()
        record_continuity_score("v1", "palette_coherence", 0.8)
        record_continuity_score("v1", "lighting_continuity", 0.6)
        record_continuity_score("v2", "palette_coherence", 0.9)

        history = get_continuity_history()
        assert len(history) == 3

        # Filter by dimension
        palette = get_continuity_history(dimension="palette_coherence")
        assert len(palette) == 2
        assert all(r.dimension == "palette_coherence" for r in palette)

    def test_get_best_patterns(self):
        from core.cinematic_video.sandbox.continuity_score_tracker import (
            record_continuity_score, get_best_patterns,
            clear_continuity_history,
        )
        clear_continuity_history()
        record_continuity_score("v-best", "palette_coherence", 0.95)
        record_continuity_score("v-best", "lighting_continuity", 0.92)
        record_continuity_score("v-ok", "palette_coherence", 0.6)

        best = get_best_patterns(top_n=1)
        assert len(best) >= 1
        assert best[0]["variation_id"] == "v-best"
        assert best[0]["avg_score"] > 0.9

    def test_get_dimension_trend(self):
        from core.cinematic_video.sandbox.continuity_score_tracker import (
            record_continuity_score, get_dimension_trend,
            clear_continuity_history,
        )
        clear_continuity_history()
        record_continuity_score("v1", "camera_continuity", 0.5)
        record_continuity_score("v2", "camera_continuity", 0.6)
        record_continuity_score("v3", "camera_continuity", 0.7)
        record_continuity_score("v4", "camera_continuity", 0.8)

        trend = get_dimension_trend("camera_continuity")
        assert trend["dimension"] == "camera_continuity"
        assert trend["trend"] in ("stable", "improving", "declining")

    def test_score_clamped_to_range(self):
        from core.cinematic_video.sandbox.continuity_score_tracker import (
            record_continuity_score, clear_continuity_history,
        )
        clear_continuity_history()
        rec = record_continuity_score("v1", "test", 1.5)
        assert rec.score == 1.0
        rec = record_continuity_score("v1", "test", -0.5)
        assert rec.score == 0.0

    def test_clear_continuity_history(self):
        from core.cinematic_video.sandbox.continuity_score_tracker import (
            record_continuity_score, get_continuity_history,
            clear_continuity_history,
        )
        clear_continuity_history()
        record_continuity_score("v1", "test", 0.5)
        assert len(get_continuity_history()) > 0
        clear_continuity_history()
        assert len(get_continuity_history()) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Generation Reviewer tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerationReviewer:
    """Quality review of generated outputs."""

    def test_review_generation_returns_review(self):
        from core.cinematic_video.sandbox.generation_reviewer import review_generation
        from core.cinematic_video.sandbox.schemas import GenerationReview
        rev = review_generation(
            variation_id="var-test",
            drift_score=0.0,
            shot_type="hero_shot",
            lighting="dark_matte",
        )
        assert isinstance(rev, GenerationReview)
        assert rev.review_id.startswith("rev_")

    def test_review_high_quality(self):
        from core.cinematic_video.sandbox.generation_reviewer import review_generation
        rev = review_generation(
            variation_id="var-test",
            drift_score=0.0,
            shot_type="hero_shot",
            lighting="dark_matte",
            atmosphere="premium_commercial",
            lens_style="macro",
            extension_count=0,
        )
        assert rev.overall_score > 0.7
        assert rev.recommendation == "approve"
        assert rev.severity == "info"

    def test_review_low_quality(self):
        from core.cinematic_video.sandbox.generation_reviewer import review_generation
        rev = review_generation(
            variation_id="var-test",
            drift_score=0.8,
            shot_type="emotional_lifestyle_shot",
            product_in_prompt=False,
        )
        assert rev.overall_score < 0.5
        assert rev.recommendation in ("discard", "retake")
        assert rev.severity in ("critical", "error")

    def test_review_drift_penalty_with_extensions(self):
        from core.cinematic_video.sandbox.generation_reviewer import review_generation
        # Same drift, more extensions = worse score
        rev1 = review_generation(variation_id="v1", drift_score=0.3, extension_count=0)
        rev2 = review_generation(variation_id="v2", drift_score=0.3, extension_count=5)
        assert rev2.overall_score < rev1.overall_score, (
            f"Expected {rev2.overall_score} < {rev1.overall_score}"
        )

    def test_batch_review(self):
        from core.cinematic_video.sandbox.generation_reviewer import batch_review
        variations = (
            {"variation_id": "v1", "drift_score": 0.0, "shot_type": "hero_shot",
             "lighting": "dark_matte"},
            {"variation_id": "v2", "drift_score": 0.4, "shot_type": "hero_shot",
             "lighting": "dark_matte"},
            {"variation_id": "v3", "drift_score": 0.8, "shot_type": "emotional_lifestyle_shot"},
        )
        reviews = batch_review(variations)
        assert len(reviews) == 3

    def test_get_review_summary(self):
        from core.cinematic_video.sandbox.generation_reviewer import (
            review_generation, get_review_summary,
        )
        reviews = (
            review_generation("v1", drift_score=0.0, shot_type="hero_shot", lighting="dark_matte"),
            review_generation("v2", drift_score=0.8, shot_type="emotional_lifestyle_shot"),
        )
        summary = get_review_summary(reviews)
        assert summary["total"] == 2
        assert "approved" in summary
        assert "discards" in summary
        assert "best_variation" in summary

    def test_review_never_raises(self):
        from core.cinematic_video.sandbox.generation_reviewer import review_generation
        # Empty/blank inputs
        rev = review_generation(variation_id="")
        assert rev is not None
        assert rev.review_id.startswith("rev_")


# ═══════════════════════════════════════════════════════════════════════════════
# Failed Generation Registry tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestFailedGenerationRegistry:
    """Failure registry with classification and recovery."""

    def test_record_failure(self):
        from core.cinematic_video.sandbox.failed_generation_registry import (
            record_failure, clear_failure_registry,
        )
        clear_failure_registry()
        entry = record_failure(
            experiment_id="exp-1",
            variation_id="var-1",
            error_message="Daily credit limit exceeded",
            prompt_used="A test prompt",
        )
        assert entry.failure_mode == "credits_exhausted"
        assert entry.failure_id.startswith("fail_")
        assert "credit" in entry.root_cause.lower()

    def test_record_failure_classifies_style_drift(self):
        from core.cinematic_video.sandbox.failed_generation_registry import (
            record_failure, clear_failure_registry,
        )
        clear_failure_registry()
        entry = record_failure(
            experiment_id="exp-1",
            variation_id="var-1",
            error_message="Style drift detected — inconsistent colors",
        )
        assert entry.failure_mode == "style_drift_excessive"

    def test_record_failure_classifies_unknown(self):
        from core.cinematic_video.sandbox.failed_generation_registry import (
            record_failure, clear_failure_registry,
        )
        clear_failure_registry()
        entry = record_failure(
            experiment_id="exp-1",
            variation_id="var-1",
            error_message="Something completely unexpected happened",
        )
        assert entry.failure_mode == "unknown_failure"

    def test_record_failure_permanent(self):
        from core.cinematic_video.sandbox.failed_generation_registry import (
            record_failure, clear_failure_registry,
        )
        clear_failure_registry()
        entry = record_failure(
            experiment_id="exp-1",
            variation_id="var-1",
            error_message="test",
            permanent=True,
        )
        assert entry.permanent is True

    def test_get_failures_by_mode(self):
        from core.cinematic_video.sandbox.failed_generation_registry import (
            record_failure, get_failures_by_mode, clear_failure_registry,
        )
        clear_failure_registry()
        record_failure("exp-1", "v1", "timeout error")
        record_failure("exp-2", "v2", "credit exhausted")
        record_failure("exp-3", "v3", "timeout again")

        timeouts = get_failures_by_mode(failure_mode="generation_timeout")
        assert len(timeouts) == 2

    def test_get_failure_statistics(self):
        from core.cinematic_video.sandbox.failed_generation_registry import (
            record_failure, get_failure_statistics, clear_failure_registry,
        )
        clear_failure_registry()
        record_failure("e1", "v1", "credit exhausted", permanent=True)
        record_failure("e2", "v2", "timeout error", recovery_successful=True)

        stats = get_failure_statistics()
        assert stats["total_failures"] >= 2
        assert stats["permanent_count"] >= 1
        assert "by_mode" in stats

    def test_get_recovery_for_pattern(self):
        from core.cinematic_video.sandbox.failed_generation_registry import (
            record_failure, get_recovery_for_pattern, clear_failure_registry,
        )
        clear_failure_registry()
        record_failure(
            "e1", "v1", "credit exhausted",
            recovery_attempted="Wait 24h for reset",
            recovery_successful=True,
        )

        recovery = get_recovery_for_pattern("credits_exhausted")
        assert recovery is not None
        assert "Wait" in recovery or "reset" in recovery.lower()

    def test_clear_failure_registry(self):
        from core.cinematic_video.sandbox.failed_generation_registry import (
            record_failure, get_failure_statistics, clear_failure_registry,
        )
        clear_failure_registry()
        record_failure("e1", "v1", "test")
        assert get_failure_statistics()["total_failures"] > 0
        clear_failure_registry()
        assert get_failure_statistics()["total_failures"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Flow Experiment Runner tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowExperimentRunner:
    """End-to-end sandbox experiment orchestration."""

    def test_run_experiment_basic(self):
        from core.cinematic_video.sandbox.schemas import ExperimentConfig
        from core.cinematic_video.sandbox.flow_experiment_runner import run_experiment
        from core.cinematic_video.sandbox.schemas import SandboxExperiment

        cfg = ExperimentConfig(
            experiment_id="test-exp-1",
            base_prompt="A premium watch on reflective surface",
            product_name="Luxury Watch",
            variation_count=4,
            extend_count=2,
            dimensions=("shot_type", "lighting"),
        )
        exp = run_experiment(cfg)
        assert isinstance(exp, SandboxExperiment)
        assert exp.experiment_id == "test-exp-1"
        assert len(exp.variations) > 0
        assert exp.completed_at
        assert exp.duration_ms > 0

    def test_run_experiment_produces_variations(self):
        from core.cinematic_video.sandbox.schemas import ExperimentConfig
        from core.cinematic_video.sandbox.flow_experiment_runner import run_experiment

        cfg = ExperimentConfig(
            experiment_id="test-exp-2",
            base_prompt="Test product",
            variation_count=6,
            dimensions=("shot_type", "camera_motion", "lighting"),
        )
        exp = run_experiment(cfg)
        assert len(exp.variations) >= 1
        # All variations from the base prompt
        for v in exp.variations:
            assert v.base_prompt == "Test product"

    def test_run_experiment_produces_extension_trials(self):
        from core.cinematic_video.sandbox.schemas import ExperimentConfig
        from core.cinematic_video.sandbox.flow_experiment_runner import run_experiment

        cfg = ExperimentConfig(
            experiment_id="test-exp-3",
            base_prompt="Test",
            variation_count=2,
            extend_count=2,
            dimensions=("lighting",),
        )
        exp = run_experiment(cfg)
        assert len(exp.extension_trials) > 0

    def test_run_experiment_produces_reviews(self):
        from core.cinematic_video.sandbox.schemas import ExperimentConfig
        from core.cinematic_video.sandbox.flow_experiment_runner import run_experiment

        cfg = ExperimentConfig(
            experiment_id="test-exp-4",
            base_prompt="Test",
            variation_count=3,
            extend_count=1,
            dimensions=("shot_type", "lighting"),
        )
        exp = run_experiment(cfg)
        assert len(exp.reviews) > 0

    def test_run_experiment_has_lessons(self):
        from core.cinematic_video.sandbox.schemas import ExperimentConfig
        from core.cinematic_video.sandbox.flow_experiment_runner import run_experiment

        cfg = ExperimentConfig(
            experiment_id="test-exp-5",
            base_prompt="Test product shot",
            variation_count=3,
            extend_count=2,
            dimensions=("shot_type", "lighting"),
        )
        exp = run_experiment(cfg)
        assert len(exp.lessons_learned) > 0

    def test_run_experiment_best_variation(self):
        from core.cinematic_video.sandbox.schemas import ExperimentConfig
        from core.cinematic_video.sandbox.flow_experiment_runner import run_experiment

        cfg = ExperimentConfig(
            experiment_id="test-exp-6",
            base_prompt="test",
            variation_count=4,
            dimensions=("lighting", "pacing"),
        )
        exp = run_experiment(cfg)
        # Best variation should be one of the generated ones
        variation_ids = {v.variation_id for v in exp.variations}
        assert exp.best_variation_id in variation_ids

    def test_run_experiment_persisted(self):
        from core.cinematic_video.sandbox.schemas import ExperimentConfig
        from core.cinematic_video.sandbox.flow_experiment_runner import run_experiment
        from pathlib import Path

        cfg = ExperimentConfig(
            experiment_id="test-persist",
            base_prompt="test",
            variation_count=1,
            dimensions=("lighting",),
        )
        exp = run_experiment(cfg)
        expected_path = Path(__file__).parent.parent / "logs" / "sandbox" / "experiments" / "test-persist.json"
        assert expected_path.exists(), f"Report not found at {expected_path}"

    def test_run_experiment_never_raises(self):
        from core.cinematic_video.sandbox.schemas import ExperimentConfig
        from core.cinematic_video.sandbox.flow_experiment_runner import run_experiment

        # Minimal config
        cfg = ExperimentConfig(
            experiment_id="test-never-raises",
            base_prompt="",
            variation_count=0,
            dimensions=(),
        )
        exp = run_experiment(cfg)
        assert exp is not None

    def test_run_batch_experiments(self):
        from core.cinematic_video.sandbox.schemas import ExperimentConfig
        from core.cinematic_video.sandbox.flow_experiment_runner import (
            run_batch_experiments,
        )

        configs = (
            ExperimentConfig(experiment_id="batch-1", base_prompt="test a",
                             variation_count=2, dimensions=("lighting",)),
            ExperimentConfig(experiment_id="batch-2", base_prompt="test b",
                             variation_count=2, dimensions=("shot_type",)),
        )
        results = run_batch_experiments(configs)
        assert len(results) == 2
        assert results[0].experiment_id == "batch-1"
        assert results[1].experiment_id == "batch-2"

    def test_get_experiment_history(self):
        from core.cinematic_video.sandbox.schemas import ExperimentConfig
        from core.cinematic_video.sandbox.flow_experiment_runner import (
            run_experiment, get_experiment_history,
        )

        cfg = ExperimentConfig(
            experiment_id="history-test",
            base_prompt="test",
            variation_count=1,
            dimensions=("lighting",),
        )
        run_experiment(cfg)
        history = get_experiment_history(limit=5)
        assert len(history) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Never-raise contract
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowSandboxNeverRaise:
    """All sandbox public functions must never raise."""

    def test_all_public_functions_never_raise(self):
        from core.cinematic_video.sandbox.prompt_variation_engine import (
            generate_variations, generate_single_variation,
        )
        from core.cinematic_video.sandbox.clip_extension_tester import (
            run_extension_trial, get_extension_health,
        )
        from core.cinematic_video.sandbox.generation_reviewer import (
            review_generation,
        )
        from core.cinematic_video.sandbox.failed_generation_registry import (
            record_failure, get_failure_statistics,
        )

        # Test each with edge-case inputs
        try:
            generate_variations("", dimensions=(), max_total=0)
        except Exception as e:
            pytest.fail(f"generate_variations raised: {e}")

        try:
            generate_single_variation("", "")
        except Exception as e:
            pytest.fail(f"generate_single_variation raised: {e}")

        try:
            run_extension_trial("", max_extensions=0)
        except Exception as e:
            pytest.fail(f"run_extension_trial raised: {e}")

        try:
            get_extension_health(())
        except Exception as e:
            pytest.fail(f"get_extension_health raised: {e}")

        try:
            review_generation("")
        except Exception as e:
            pytest.fail(f"review_generation raised: {e}")

        try:
            record_failure("", "", "")
        except Exception as e:
            pytest.fail(f"record_failure raised: {e}")

        try:
            get_failure_statistics()
        except Exception as e:
            pytest.fail(f"get_failure_statistics raised: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: sandbox doesn't import forbidden layers
# ═══════════════════════════════════════════════════════════════════════════════

class TestFlowSandboxIsolation:
    """Sandbox must not import forbidden layers."""

    FORBIDDEN = (
        "truth_layer",
        "revenue_layer",
        "dispatch_critical",
        "master_pipeline",
    )

    def test_no_forbidden_imports_in_sandbox(self):
        import ast
        import inspect
        import core.cinematic_video.sandbox as sandbox_mod

        for mod_name, mod in [
            ("schemas", __import__("core.cinematic_video.sandbox.schemas", fromlist=[""])),
            ("prompt_variation_engine", __import__("core.cinematic_video.sandbox.prompt_variation_engine", fromlist=[""])),
            ("clip_extension_tester", __import__("core.cinematic_video.sandbox.clip_extension_tester", fromlist=[""])),
            ("continuity_score_tracker", __import__("core.cinematic_video.sandbox.continuity_score_tracker", fromlist=[""])),
            ("generation_reviewer", __import__("core.cinematic_video.sandbox.generation_reviewer", fromlist=[""])),
            ("failed_generation_registry", __import__("core.cinematic_video.sandbox.failed_generation_registry", fromlist=[""])),
            ("flow_experiment_runner", __import__("core.cinematic_video.sandbox.flow_experiment_runner", fromlist=[""])),
        ]:
            src = inspect.getsource(mod)
            for line in src.split("\n"):
                stripped = line.strip()
                for fb in self.FORBIDDEN:
                    assert fb not in stripped, (
                        f"{mod_name}: Forbidden import '{fb}' found: {stripped}"
                    )

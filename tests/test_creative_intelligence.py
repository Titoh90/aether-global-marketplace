#!/usr/bin/env python3
"""
Tests for Hermes Creative Intelligence v2.

The layer is additive-only: it reads existing IMPERIO signals and writes only
creative intelligence state/fingerprint files. It must never post or mutate the
deterministic core.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
sys.path.insert(0, str(IMPERIO_ROOT))


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _seed_creative_root(tmp_path: Path) -> Path:
    root = tmp_path / "IMPERIO_ROOT"
    revenue = root / "REVENUE"
    memory = root / "memory" / "competitive_intelligence"

    _write_json(
        revenue / "campaigns.json",
        {
            "campaigns": {
                "B001": {
                    "campaign_id": "B001",
                    "asin": "B001",
                    "product_name": "Premium Desk Lamp",
                    "category": "home",
                    "phase": "EXPLORATION",
                    "posts_count": 4,
                    "performance_score": 61,
                    "primary_mode": "EMOTIONAL_LIFESTYLE",
                    "secondary_modes": ["CINEMATIC_STORY", "AMAZON_BESTSELLER"],
                    "visual_identity": {"mood": "warm premium", "composition": "centered hero"},
                    "hook_styles": ["lifestyle_desire", "social_proof_shock"],
                },
                "B002": {
                    "campaign_id": "B002",
                    "asin": "B002",
                    "product_name": "Minimal Headphones",
                    "category": "electronics",
                    "phase": "VALIDATION",
                    "posts_count": 7,
                    "performance_score": 44,
                    "primary_mode": "EMOTIONAL_LIFESTYLE",
                    "secondary_modes": ["CINEMATIC_HERO"],
                    "visual_identity": {"mood": "clean studio", "composition": "centered hero"},
                    "hook_styles": ["precision_reveal"],
                },
            }
        },
    )
    _write_json(
        revenue / "gdal_report.json",
        {
            "resolution_actions": [
                {"priority": "HIGH", "action": "BLOCK_LOW_QUALITY_PUBLISH", "detail": "ASL weak"}
            ],
            "stability_risks": ["CPBIE platform synchronization risk active"],
        },
    )
    _write_json(
        revenue / "uck_output.json",
        {
            "outputs": {
                "B001": {
                    "ready_to_publish": False,
                    "state_updates": {"risk_flags": ["WEAK_EMOTION"]},
                    "platform_meta": {"instagram": {"angle": "identity"}},
                }
            }
        },
    )
    _write_json(
        revenue / "brand_report.json",
        {
            "visual_consistency_score": 55,
            "tone_consistency_score": 82,
            "identity_risk_signals": ["visual drift risk"],
            "content_mix_adjustments": [{"action": "ADD_1_MORE_EDUCATIONAL_POSTS_NEXT_10"}],
        },
    )
    (revenue / "engagement_shadow_log.jsonl").write_text(
        json.dumps({"intent": "question", "comment": "does it work?", "proposed_reply": "yes"}) + "\n"
    )
    _write_json(
        root / "creative_engine" / "style_director.json",
        {
            "categories": {
                "home": {"style_name": "IKEA Premium", "prompt_prefix": "warm home"},
                "electronics": {"style_name": "Apple Keynote", "prompt_prefix": "clean tech"},
                "beauty": {"style_name": "Sephora Luxury", "prompt_prefix": "beauty macro"},
            }
        },
    )
    _write_json(
        memory / "ci_report_2026-05-30.json",
        {
            "trends": [
                {"style": "minimal_clean", "viral_score": 0.72, "patterns": ["question_led"]}
            ]
        },
    )
    return root


def test_signal_store_builds_unified_state_without_pipeline_mutation(tmp_path):
    from core.creative_intelligence.signal_store import build_creative_signal_state

    root = _seed_creative_root(tmp_path)
    forbidden_before = {
        "truth_guard": (root / "core" / "truth" / "truth_guard.py").exists(),
        "posts_log": (root / "REVENUE" / "posts_log.jsonl").exists(),
    }

    state = build_creative_signal_state(root=root, persist=True)

    state_file = root / "REVENUE" / "creative_intelligence_state.json"
    assert state_file.exists()
    assert state["version"] == 2
    assert state["sources"]["campaigns"] == 2
    assert "EMOTIONAL_LIFESTYLE" in state["style_usage"]
    assert any("Repeated creative mode" in warning for warning in state["warnings"])
    assert any(risk["source"] == "gdal" for risk in state["risk_flags"])
    assert forbidden_before["truth_guard"] == (root / "core" / "truth" / "truth_guard.py").exists()
    assert forbidden_before["posts_log"] == (root / "REVENUE" / "posts_log.jsonl").exists()


def test_creative_brief_generator_returns_structured_hypotheses(tmp_path):
    from core.creative_intelligence.creative_brief_generator import generate_creative_brief

    root = _seed_creative_root(tmp_path)
    brief = generate_creative_brief("B001", root=root)

    assert set(brief) == {
        "product_id",
        "campaign_angle",
        "visual_style_candidates",
        "hook_variants",
        "platform_strategy",
        "risk_flags",
        "confidence",
    }
    assert brief["product_id"] == "B001"
    assert brief["visual_style_candidates"]
    assert len(brief["hook_variants"]) >= 3
    assert "instagram" in brief["platform_strategy"]
    assert 0.0 <= brief["confidence"] <= 1.0


def test_visual_diversity_engine_scores_repetition_and_cooldown(tmp_path):
    from core.creative_intelligence.visual_diversity_engine import score_visual_diversity

    root = _seed_creative_root(tmp_path)
    result = score_visual_diversity("B001", root=root)

    assert result["product_id"] == "B001"
    assert result["diversity_score"] < 1.0
    assert result["recommended_style_variants"]
    assert all(style != "EMOTIONAL_LIFESTYLE" for style in result["recommended_style_variants"])
    assert result["repetition_warnings"]


def test_inspiration_fingerprints_store_metadata_only(tmp_path):
    from core.creative_intelligence.inspiration_intelligence import ingest_fingerprint

    root = _seed_creative_root(tmp_path)
    result = ingest_fingerprint(
        {
            "source": "manual",
            "style_type": "minimal_clean",
            "composition_structure": "negative_space",
            "hook_type": "question_led",
            "cta_type": "soft_mention",
            "palette_family": "warm_neutral",
            "engagement_pattern_type": "save_for_later",
            "raw_caption": "this must not be persisted",
            "image_url": "https://example.com/do-not-store.jpg",
        },
        root=root,
    )

    assert result["stored"] is True
    stored = json.loads((root / "memory" / "creative_intelligence" / "inspiration_fingerprints.json").read_text())
    fingerprint = stored["fingerprints"][0]
    assert "raw_caption" not in fingerprint
    assert "image_url" not in fingerprint
    assert fingerprint["style_type"] == "minimal_clean"


def test_telegram_creative_commands_are_read_only(monkeypatch, tmp_path):
    import interfaces.telegram.command_router as command_router

    root = _seed_creative_root(tmp_path)
    monkeypatch.setattr(command_router, "IMPERIO_ROOT", root)

    router = command_router.CommandRouter()
    text = asyncio.run(router.handle("/creative", "", chat_id=123))

    assert "3 ideas" in text
    assert "2 warnings" in text
    assert "1 opportunity" in text
    assert "1 risk" in text
    assert not (root / "REVENUE" / "posts_log.jsonl").exists()


# ── Mock hermes_core factory for /digest, /meta, /weekly handler tests ──

class _MockHermesCore:
    """Mock hermes_core module with controllable return values."""

    def __init__(self):
        self.meta_cognitive_calls: list[tuple[str, str]] = []
        self.weekly_digest_calls: int = 0
        self._meta_result: dict = {"status": "success", "formatted": "default meta output"}
        self._weekly_result: dict = {"status": "success", "formatted": "default weekly output"}

    def handle_meta_cognitive(self, text: str, action: str) -> dict:
        self.meta_cognitive_calls.append((text, action))
        return self._meta_result

    def handle_weekly_digest(self) -> dict:
        self.weekly_digest_calls += 1
        return self._weekly_result


def _install_mock_hermes(monkeypatch, mock_mod: _MockHermesCore):
    """Register the mock hermes_core in sys.modules so local imports resolve."""
    import sys as _sys

    monkeypatch.setitem(_sys.modules, "hermes_core", mock_mod)
    return mock_mod


# ── /digest handler tests ──

class TestDigestHandler:

    def test_digest_returns_formatted_output(self, monkeypatch):
        mock = _MockHermesCore()
        mock._meta_result = {"status": "success", "formatted": "*DAILY CREATIVE DIGEST*\n3 ideas, 2 warnings"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/digest", "", chat_id=123))

        assert "DAILY CREATIVE DIGEST" in text
        assert "3 ideas" in text

    def test_digest_passes_digest_action_to_hermes_core(self, monkeypatch):
        mock = _MockHermesCore()
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        asyncio.run(router.handle("/digest", "", chat_id=456))

        assert len(mock.meta_cognitive_calls) == 1
        assert mock.meta_cognitive_calls[0] == ("", "digest")

    def test_digest_handles_error_status(self, monkeypatch):
        mock = _MockHermesCore()
        mock._meta_result = {"status": "error", "error": "Log file missing"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/digest", "", chat_id=123))

        assert text.startswith("Error:")
        assert "Log file missing" in text

    def test_digest_handles_missing_formatted_key(self, monkeypatch):
        mock = _MockHermesCore()
        mock._meta_result = {"status": "success"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/digest", "", chat_id=123))

        assert text == "No output"

    def test_digest_propagates_handler_exceptions(self, monkeypatch):
        """If handle_meta_cognitive raises, the exception propagates (handler does NOT swallow)."""
        class _BrokenModule:
            def handle_meta_cognitive(self, *a, **kw):
                raise RuntimeError("Simulated crash in hermes_core")

        mock = _BrokenModule()
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()

        with pytest.raises(RuntimeError, match="Simulated crash in hermes_core"):
            asyncio.run(router.handle("/digest", "", chat_id=123))


# ── /meta handler tests ──

class TestMetaHandler:

    def test_meta_returns_formatted_output(self, monkeypatch):
        mock = _MockHermesCore()
        mock._meta_result = {"status": "success", "formatted": "*META-COGNITIVE STATE*\nRisk: LOW"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/meta", "", chat_id=123))

        assert "META-COGNITIVE STATE" in text
        assert "Risk: LOW" in text

    def test_meta_passes_meta_action_to_hermes_core(self, monkeypatch):
        mock = _MockHermesCore()
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        asyncio.run(router.handle("/meta", "", chat_id=789))

        assert len(mock.meta_cognitive_calls) == 1
        assert mock.meta_cognitive_calls[0] == ("", "meta")

    def test_meta_handles_error_status(self, monkeypatch):
        mock = _MockHermesCore()
        mock._meta_result = {"status": "error", "error": "Orchestrator timeout"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/meta", "", chat_id=123))

        assert text.startswith("Error:")
        assert "Orchestrator timeout" in text

    def test_meta_handles_completely_empty_dict(self, monkeypatch):
        mock = _MockHermesCore()
        mock._meta_result = {}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/meta", "", chat_id=123))

        # No status key → not "success" → falls through to error branch
        assert text.startswith("Error:")
        assert "unknown" in text


# ── /weekly handler tests ──

class TestWeeklyHandler:

    def test_weekly_returns_formatted_output(self, monkeypatch):
        mock = _MockHermesCore()
        mock._weekly_result = {"status": "success", "formatted": "*WEEKLY CREATIVE SUMMARY*\n7 days, 12 cycles"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/weekly", "", chat_id=123))

        assert "WEEKLY CREATIVE SUMMARY" in text
        assert "12 cycles" in text

    def test_weekly_calls_handle_weekly_digest_exactly_once(self, monkeypatch):
        mock = _MockHermesCore()
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        asyncio.run(router.handle("/weekly", "", chat_id=123))

        assert mock.weekly_digest_calls == 1

    def test_weekly_handles_error_status(self, monkeypatch):
        mock = _MockHermesCore()
        mock._weekly_result = {"status": "error", "error": "No cycles in range"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/weekly", "", chat_id=123))

        assert text.startswith("Error:")
        assert "No cycles in range" in text

    def test_weekly_handles_missing_formatted_key(self, monkeypatch):
        mock = _MockHermesCore()
        mock._weekly_result = {"status": "success"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/weekly", "", chat_id=123))

        assert text == "No output"


# ── regression: all three commands listed in /help ──

class TestHelpIncludesNewCommands:

    def test_help_includes_digest_meta_weekly(self, monkeypatch, tmp_path):
        import interfaces.telegram.command_router as command_router
        root = _seed_creative_root(tmp_path)
        monkeypatch.setattr(command_router, "IMPERIO_ROOT", root)

        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/help", "", chat_id=123))

        assert "/digest — Daily Creative Digest" in text
        assert "/meta — Meta-cognitive system state" in text
        assert "/weekly — Weekly creative summary (7-day trends)" in text

    def test_unknown_command_does_not_crash(self, monkeypatch, tmp_path):
        import interfaces.telegram.command_router as command_router
        monkeypatch.setattr(command_router, "IMPERIO_ROOT", Path(tmp_path))

        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/nonexistent", "", chat_id=123))

        assert "desconocido" in text.lower()
        assert "/help" in text


# ── cross-verification: /digest and /meta route to different actions ──

def test_digest_and_meta_use_different_actions(monkeypatch):
    """Ensure /digest → "digest" and /meta → "meta" — not a copy-paste bug."""
    mock = _MockHermesCore()
    _install_mock_hermes(monkeypatch, mock)

    import interfaces.telegram.command_router as command_router
    router = command_router.CommandRouter()

    asyncio.run(router.handle("/digest", "", chat_id=123))
    asyncio.run(router.handle("/meta", "", chat_id=456))

    assert mock.meta_cognitive_calls == [("", "digest"), ("", "meta")]


# ── direct tests for _route_meta_cognitive shared helper ──

class TestRouteMetaCognitive:
    """Test the shared _route_meta_cognitive method directly (both paths)."""

    # ── is_weekly=False path (handle_meta_cognitive) ──

    def test_digest_path_returns_formatted(self, monkeypatch):
        mock = _MockHermesCore()
        mock._meta_result = {"status": "success", "formatted": "digest output here"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router._route_meta_cognitive("digest"))

        assert text == "digest output here"

    def test_meta_path_returns_formatted(self, monkeypatch):
        mock = _MockHermesCore()
        mock._meta_result = {"status": "success", "formatted": "meta output here"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router._route_meta_cognitive("meta"))

        assert text == "meta output here"

    def test_non_weekly_passes_action_to_hermes_core(self, monkeypatch):
        mock = _MockHermesCore()
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        asyncio.run(router._route_meta_cognitive("digest"))

        assert len(mock.meta_cognitive_calls) == 1
        assert mock.meta_cognitive_calls[0] == ("", "digest")

    def test_non_weekly_error_status(self, monkeypatch):
        mock = _MockHermesCore()
        mock._meta_result = {"status": "error", "error": "something broke"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router._route_meta_cognitive("meta"))

        assert text.startswith("Error:")
        assert "something broke" in text

    def test_non_weekly_missing_formatted_key(self, monkeypatch):
        mock = _MockHermesCore()
        mock._meta_result = {"status": "success"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router._route_meta_cognitive("digest"))

        assert text == "No output"

    def test_non_weekly_empty_dict(self, monkeypatch):
        mock = _MockHermesCore()
        mock._meta_result = {}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router._route_meta_cognitive("meta"))

        assert text.startswith("Error:")
        assert "unknown" in text

    # ── is_weekly=True path (handle_weekly_digest) ──

    def test_weekly_path_returns_formatted(self, monkeypatch):
        mock = _MockHermesCore()
        mock._weekly_result = {"status": "success", "formatted": "weekly output here"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router._route_meta_cognitive(is_weekly=True))

        assert text == "weekly output here"

    def test_weekly_path_calls_handle_weekly_digest(self, monkeypatch):
        mock = _MockHermesCore()
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        asyncio.run(router._route_meta_cognitive(is_weekly=True))

        assert mock.weekly_digest_calls == 1
        assert mock.meta_cognitive_calls == []  # not the meta path

    def test_weekly_error_status(self, monkeypatch):
        mock = _MockHermesCore()
        mock._weekly_result = {"status": "error", "error": "weekly failed"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router._route_meta_cognitive(is_weekly=True))

        assert text.startswith("Error:")
        assert "weekly failed" in text

    def test_weekly_missing_formatted_key(self, monkeypatch):
        mock = _MockHermesCore()
        mock._weekly_result = {"status": "success"}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router._route_meta_cognitive(is_weekly=True))

        assert text == "No output"

    def test_weekly_empty_dict(self, monkeypatch):
        mock = _MockHermesCore()
        mock._weekly_result = {}
        _install_mock_hermes(monkeypatch, mock)

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router._route_meta_cognitive(is_weekly=True))

        assert text.startswith("Error:")
        assert "unknown" in text


# ── /analyze handler tests ──

class _MockOrchestrator:
    """Mock HermesMetaOrchestrator for /analyze tests."""

    def __init__(self, formatted_output: str = "", should_fail: bool = False):
        self.run_cycle_calls: int = 0
        self.enrich_calls: int = 0
        self._formatted = formatted_output or (
            "🧠 *ANÁLISIS LLM*\n### INSIGHTS\n- Test insight 1\n- Test insight 2\n- Test insight 3"
        )
        self._should_fail = should_fail
        self._fail_error = "LLM timeout"

    def run_cycle(self, persist: bool = True):
        self.run_cycle_calls += 1
        # Return a minimal MetaCognitiveOutput-like object
        return _FakeOutput()

    async def enrich_with_llm(self, output=None) -> str:
        self.enrich_calls += 1
        if self._should_fail:
            raise RuntimeError(self._fail_error)
        return self._formatted


class _FakeOutput:
    """Minimal stub that satisfies enrich_with_llm(output=...)."""
    pass


class TestAnalyzeHandler:

    def test_analyze_returns_formatted_output(self, monkeypatch):
        mock = _MockOrchestrator(
            formatted_output="🧠 *ANÁLISIS LLM*\n### INSIGHTS\n- Revenue trending up\n- Style fatigue detected\n- Viral opportunity: smart home"
        )
        monkeypatch.setenv("FEATURE_LLM_ANALYSIS", "1")
        monkeypatch.setattr(
            "core.meta_cognitive.orchestrator.HermesMetaOrchestrator",
            lambda: mock,
        )

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/analyze", "", chat_id=123))

        assert "ANÁLISIS LLM" in text
        assert "INSIGHTS" in text
        assert "Revenue trending up" in text
        assert "Viral opportunity" in text

    def test_analyze_runs_cycle_and_enriches(self, monkeypatch):
        mock = _MockOrchestrator()
        monkeypatch.setenv("FEATURE_LLM_ANALYSIS", "1")
        monkeypatch.setattr(
            "core.meta_cognitive.orchestrator.HermesMetaOrchestrator",
            lambda: mock,
        )

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        asyncio.run(router.handle("/analyze", "", chat_id=456))

        assert mock.run_cycle_calls == 1
        assert mock.enrich_calls == 1

    def test_analyze_disabled_when_feature_flag_off(self, monkeypatch):
        mock = _MockOrchestrator()
        monkeypatch.setenv("FEATURE_LLM_ANALYSIS", "0")
        monkeypatch.setattr(
            "core.meta_cognitive.orchestrator.HermesMetaOrchestrator",
            lambda: mock,
        )

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/analyze", "", chat_id=123))

        assert "LLM analysis" in text
        assert "FEATURE_LLM_ANALYSIS" in text
        assert mock.run_cycle_calls == 0  # never called
        assert mock.enrich_calls == 0

    def test_analyze_handles_llm_failure(self, monkeypatch):
        mock = _MockOrchestrator(should_fail=True)
        monkeypatch.setenv("FEATURE_LLM_ANALYSIS", "1")
        monkeypatch.setattr(
            "core.meta_cognitive.orchestrator.HermesMetaOrchestrator",
            lambda: mock,
        )

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/analyze", "", chat_id=123))

        assert text.startswith("Error:")
        assert "LLM timeout" in text

    def test_analyze_listed_in_help(self, monkeypatch):
        mock = _MockOrchestrator()
        monkeypatch.setattr(
            "core.meta_cognitive.orchestrator.HermesMetaOrchestrator",
            lambda: mock,
        )

        import interfaces.telegram.command_router as command_router
        router = command_router.CommandRouter()
        text = asyncio.run(router.handle("/help", "", chat_id=123))

        assert "/analyze" in text
        assert "LLM-enriched" in text
        assert "FEATURE_LLM_ANALYSIS" in text

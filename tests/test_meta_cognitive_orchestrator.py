#!/usr/bin/env python3
"""
Unit tests for HermesMetaOrchestrator.build_weekly_summary().

Covers:
  - Empty cycles list
  - Single cycle (no trends, stable defaults)
  - Multi-cycle fatigue trend: improving, worsening, stable
  - Multi-cycle risk trend: improving, worsening, stable
  - Edge cases: missing keys, None values, mixed partial/full data
  - Output format contracts: all expected section headers present
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
sys.path.insert(0, str(IMPERIO_ROOT))


# ── Helper: build a minimal cycle dict compatible with to_dict() format ──────

def _make_cycle(
    fatigue: float = 0.1,
    risk_level: str = "LOW",
    ideas: list[str] | None = None,
    warnings: list[str] | None = None,
    opportunity: str = "",
    experiment: str = "",
    duration_ms: int = 500,
) -> dict:
    return {
        "state": {
            "creative": {
                "global_style_fatigue": fatigue,
            },
            "risk": {
                "overall_risk_level": risk_level,
            },
        },
        "decisions": {
            "ideas": ideas or [],
            "warnings": warnings or [],
            "strategic_opportunity": opportunity,
            "recommended_experiment": experiment,
        },
        "cycle_duration_ms": duration_ms,
    }


# ── Test: empty cycles ───────────────────────────────────────────────────────

def test_empty_cycles_returns_no_data_placeholders():
    """Empty cycles list should not crash, should return 'No data' sections."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    result = HermesMetaOrchestrator.build_weekly_summary([])
    assert isinstance(result, str)
    assert len(result) > 0
    # Verify all expected section headers exist even with no data
    assert "FATIGUE:" in result
    assert "RISK:" in result
    assert "IDEAS:" in result
    assert "WARNINGS:" in result
    assert "STATS:" in result
    # Verify the "No data" convention
    assert "No data" in result
    # Verify cycles=0 in stats
    assert "Cycles: 0" in result


# ── Test: single cycle ───────────────────────────────────────────────────────

def test_single_cycle_no_trend_stable():
    """Single cycle has no trend — displays start/end values, range, avg, stable."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(
            fatigue=0.25,
            risk_level="LOW",
            ideas=["Rotate 'Product X' from 'Style A' to 'Style B' (medium fatigue)"],
            warnings=["Style overuse risk active"],
            opportunity="TRENDING: 'Hot Product'",
            experiment="Style A/B Test: 'New Style' vs current",
            duration_ms=600,
        )
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)

    # Fatigue section: single value, stable
    assert "FATIGUE TREND:" in result
    assert "Start: 25.00%" in result
    assert "End: 25.00%" in result
    assert "Range: 25.00%–25.00%" in result
    assert "STABLE" in result

    # Risk section: one LOW
    assert "RISK TREND:" in result
    assert "LOW: 1" in result

    # Ideas section: should detect "rotate" theme
    assert "TOP IDEAS:" in result
    assert "Rotate styles" in result

    # Warnings section
    assert "TOP WARNINGS:" in result

    # Opportunities
    assert "OPPORTUNITIES:" in result

    # Experiments
    assert "EXPERIMENTS:" in result

    # Stats
    assert "STATS:" in result
    assert "Cycles: 1" in result
    assert "Avg: 600ms" in result


def test_single_cycle_no_ideas_no_warnings():
    """Single cycle with no ideas/warnings — sections still present."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [_make_cycle(fatigue=0.0, risk_level="LOW")]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)

    assert "IDEAS:" in result
    assert "WARNINGS:" in result
    assert "OPPORTUNITIES:" not in result  # no opportunity, so section omitted
    assert "EXPERIMENTS:" not in result  # no experiment, so section omitted


# ── Test: multi-cycle fatigue trends ──────────────────────────────────────────

def test_improving_fatigue_trend():
    """Fatigue decreasing over 5 cycles → IMPROVING."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(fatigue=0.40),
        _make_cycle(fatigue=0.35),
        _make_cycle(fatigue=0.30),
        _make_cycle(fatigue=0.25),
        _make_cycle(fatigue=0.20),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "IMPROVING" in result
    assert "Start: 40.00%" in result
    assert "End: 20.00%" in result
    assert "Range: 20.00%–40.00%" in result
    assert "Avg: 30.00%" in result


def test_worsening_fatigue_trend():
    """Fatigue increasing over 4 cycles → WORSENING."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(fatigue=0.10),
        _make_cycle(fatigue=0.18),
        _make_cycle(fatigue=0.27),
        _make_cycle(fatigue=0.45),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "WORSENING" in result
    assert "Start: 10.00%" in result
    assert "End: 45.00%" in result


def test_stable_fatigue_trend_within_threshold():
    """Fatigue barely moving (within ±5 percentage points) → STABLE."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    # Difference is exactly 0.04 — within ±0.05 threshold
    cycles = [
        _make_cycle(fatigue=0.30),
        _make_cycle(fatigue=0.32),
        _make_cycle(fatigue=0.31),
        _make_cycle(fatigue=0.33),
        _make_cycle(fatigue=0.34),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "STABLE" in result


def test_stable_fatigue_exactly_same():
    """All fatigue values identical → STABLE."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [_make_cycle(fatigue=0.15) for _ in range(10)]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "STABLE" in result


# ── Test: multi-cycle risk trends ─────────────────────────────────────────────

def test_improving_risk_trend():
    """Risk going from HIGH to LOW → IMPROVING."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(risk_level="HIGH"),
        _make_cycle(risk_level="MEDIUM"),
        _make_cycle(risk_level="MEDIUM"),
        _make_cycle(risk_level="LOW"),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "IMPROVING" in result
    assert "LOW: 1" in result
    assert "MEDIUM: 2" in result
    assert "HIGH: 1" in result


def test_worsening_risk_trend():
    """Risk going from LOW to HIGH → WORSENING."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(risk_level="LOW"),
        _make_cycle(risk_level="LOW"),
        _make_cycle(risk_level="MEDIUM"),
        _make_cycle(risk_level="HIGH"),
        _make_cycle(risk_level="HIGH"),
        _make_cycle(risk_level="CRITICAL"),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "WORSENING" in result
    assert "LOW: 2" in result
    assert "HIGH: 2" in result
    assert "CRITICAL: 1" in result


def test_stable_risk_trend():
    """All risk LOW throughout → STABLE."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [_make_cycle(risk_level="LOW") for _ in range(7)]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "STABLE" in result


def test_even_split_risk_trend():
    """Equal number of HIGH in both halves → STABLE."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(risk_level="HIGH"),
        _make_cycle(risk_level="LOW"),
        _make_cycle(risk_level="LOW"),
        _make_cycle(risk_level="HIGH"),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "STABLE" in result


# ── Test: idea theme categorization ───────────────────────────────────────────

def test_idea_theme_categorization():
    """Verify _summarize_idea_theme correctly categorizes different idea types."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    test_cases = [
        ("Rotate 'X' from 'A' to 'B' (high fatigue)", "Rotate styles"),
        ("Refresh 'Y' creative hooks (score 50/100)", "Refresh hooks"),
        ("Expand visual diversity: 5 unused styles available", "Expand visual diversity"),
        ("Run an A/B split test: warm vs cool palette", "Run A/B test"),
        ("Capitalize on trending product: 'Z'", "Capitalize on trends"),
        ("Fill content gap: add commercial/CTA post variant", "Fill content gaps"),
        ("Test one mood-driven variant for top campaign", "Test new approach"),
        ("Some completely unique unfiltered idea text", "Some completely unique unfiltered idea text"),
    ]

    for idea, expected_theme in test_cases:
        theme = HermesMetaOrchestrator._summarize_idea_theme(idea)
        assert theme == expected_theme, f"Expected '{expected_theme}', got '{theme}' for idea: {idea}"


def test_long_idea_truncated():
    """Ideas longer than 60 chars are truncated with ellipsis."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    long_idea = "X" * 80  # no keywords to trigger theme shortcut
    theme = HermesMetaOrchestrator._summarize_idea_theme(long_idea)
    assert len(theme) == 63  # 60 chars + "..."
    assert theme.endswith("...")


# ── Test: idea and warning deduplication ──────────────────────────────────────

def test_duplicate_ideas_aggregated():
    """Repeated ideas counted and shown with multiplier."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(ideas=[
            "Rotate 'Product A' from 'Style X' to 'Style Y' (high fatigue)",
            "Refresh 'Product A' creative hooks (score 50/100)",
        ]),
        _make_cycle(ideas=[
            "Rotate 'Product B' from 'Style W' to 'Style Z' (medium fatigue)",
            "Refresh 'Product A' creative hooks (score 50/100)",
        ]),
        _make_cycle(ideas=[
            "Rotate 'Product C' from 'Style V' to 'Style U' (high fatigue)",
        ]),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)

    assert "Rotate styles (3×)" in result
    assert "Refresh hooks (2×)" in result
    assert "Unique: 2" in result


def test_duplicate_warnings_aggregated():
    """Repeated warnings counted and shown."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    same_warning = "Style overuse detected across multiple campaigns"
    cycles = [
        _make_cycle(warnings=[same_warning]),
        _make_cycle(warnings=[same_warning]),
        _make_cycle(warnings=[same_warning]),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "(3×)" in result


# ── Edge case: missing keys ───────────────────────────────────────────────────

def test_missing_state_key():
    """Cycle missing the 'state' key entirely."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [{"decisions": {"ideas": ["Test idea"], "warnings": [], "strategic_opportunity": "", "recommended_experiment": ""}}]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    # Should not crash
    assert "FATIGUE:" in result
    assert "No data" in result  # no fatigue values


def test_missing_creative_key():
    """Cycle with state but no creative sub-key."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [{"state": {"risk": {"overall_risk_level": "LOW"}}, "decisions": {"ideas": [], "warnings": [], "strategic_opportunity": "", "recommended_experiment": ""}}]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "FATIGUE:" in result
    assert "No data" in result


def test_missing_risk_key():
    """Cycle with state but no risk sub-key."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [{"state": {"creative": {"global_style_fatigue": 0.3}}, "decisions": {"ideas": [], "warnings": [], "strategic_opportunity": "", "recommended_experiment": ""}}]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "FATIGUE TREND:" in result  # fatigue works
    assert "RISK:" in result
    assert "No data" in result  # risk has no data


def test_missing_decisions_key():
    """Cycle missing the 'decisions' key entirely."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [{"state": {"creative": {"global_style_fatigue": 0.2}, "risk": {"overall_risk_level": "LOW"}}}]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    # Fatigue + risk should still work
    assert "FATIGUE TREND:" in result
    assert "RISK TREND:" in result
    assert "IDEAS:" in result
    assert "No data" in result


def test_completely_empty_dict():
    """Empty dict as a cycle."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [{}]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert isinstance(result, str)
    assert len(result) > 0
    # All sections should show 'No data'
    assert "FATIGUE:" in result
    assert "RISK:" in result
    assert "IDEAS:" in result
    assert "WARNINGS:" in result


# ── Edge case: None values ────────────────────────────────────────────────────

def test_none_fatigue_skipped():
    """None fatigue value skipped, not treated as 0.0."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(fatigue=0.3),  # type: ignore
        {"state": {"creative": {"global_style_fatigue": None}, "risk": {"overall_risk_level": "LOW"}}, "decisions": {"ideas": [], "warnings": [], "strategic_opportunity": "", "recommended_experiment": ""}},
        _make_cycle(fatigue=0.1),  # type: ignore
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    # Should not crash; should only use the two non-None values
    assert "Start: 30.00%" in result
    assert "End: 10.00%" in result


def test_empty_risk_level_skipped():
    """Empty string risk level should be skipped."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(risk_level=""),  # type: ignore
        _make_cycle(risk_level="LOW"),
        _make_cycle(risk_level="LOW"),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "LOW: 2" in result


# ── Edge case: mixed data quality ─────────────────────────────────────────────

def test_mixed_full_and_partial_cycles():
    """Some cycles have full data, some partial — should handle gracefully."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(fatigue=0.4, risk_level="HIGH",
                    ideas=["Rotate 'X' from 'A' to 'B'"],
                    warnings=["Warning 1"],
                    opportunity="OPP 1", experiment="EXP 1"),
        {},  # empty
        _make_cycle(fatigue=0.3, risk_level="MEDIUM",
                    ideas=["Refresh 'X' creative hooks"],
                    warnings=[]),
        {"state": {}},  # state present but empty
        _make_cycle(fatigue=0.2, risk_level="LOW",
                    ideas=["Expand visual diversity: 3 unused styles"],
                    warnings=["Warning 1"]),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)

    # Fatigue should use 3 non-empty cycles
    assert "IMPROVING" in result  # 0.4 → 0.2 = improving
    assert "Range: 20.00%–40.00%" in result

    # Risk should count valid risk levels
    assert "HIGH: 1" in result
    assert "MEDIUM: 1" in result
    assert "LOW: 1" in result

    # Ideas should aggregate across valid cycles
    assert "Rotate styles" in result
    assert "Refresh hooks" in result
    assert "Expand visual diversity" in result

    # Warnings: "Warning 1" appears twice
    assert "Warning 1 (2×)" in result


def test_large_number_of_cycles():
    """Large cycle count (50+) should not crash or produce broken output."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(
            fatigue=0.2 + (i % 5) * 0.05,
            risk_level=["LOW", "LOW", "MEDIUM", "MEDIUM", "HIGH"][i % 5],
            ideas=[f"Idea category {i % 3}: detail text here"],
            warnings=[f"Warning type {i % 4}"],
            opportunity=f"Opportunity {i % 2}" if i % 2 == 0 else "",
            experiment=f"Experiment {i % 3}" if i % 3 == 0 else "",
            duration_ms=300 + (i * 10),
        )
        for i in range(50)
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)

    # Should contain all sections
    assert "FATIGUE TREND:" in result
    assert "RISK TREND:" in result
    assert "TOP IDEAS:" in result
    assert "TOP WARNINGS:" in result
    assert "OPPORTUNITIES:" in result
    assert "EXPERIMENTS:" in result
    assert "STATS:" in result
    assert "Cycles: 50" in result


# ── Edge case: float precision ────────────────────────────────────────────────

def test_float_precision_edge_cases():
    """Very small fatigue values and edge-case float precision."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(fatigue=0.0001),
        _make_cycle(fatigue=0.0002),
        _make_cycle(fatigue=0.00015),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    # Should not crash and should detect as stable (diff < 0.05)
    assert "STABLE" in result


def test_fatigue_exactly_at_threshold():
    """Fatigue difference exactly on the 0.05 threshold → STABLE."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    # Start 0.30, end 0.35 → diff = 0.05 exactly → NOT worsening (must be > 0.05)
    cycles = [
        _make_cycle(fatigue=0.30),
        _make_cycle(fatigue=0.35),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "STABLE" in result


def test_fatigue_just_above_threshold():
    """Fatigue difference just above 0.05 → WORSENING."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    # Start 0.30, end 0.36 → diff = 0.06 → worsening
    cycles = [
        _make_cycle(fatigue=0.30),
        _make_cycle(fatigue=0.36),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "WORSENING" in result


def test_fatigue_just_below_negative_threshold():
    """Fatigue decreasing just above 0.05 → IMPROVING."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    # Start 0.40, end 0.34 → diff = -0.06 → improving
    cycles = [
        _make_cycle(fatigue=0.40),
        _make_cycle(fatigue=0.34),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    assert "IMPROVING" in result


# ── Edge case: unusual risk levels ────────────────────────────────────────────

def test_unknown_risk_levels_in_cycles():
    """Risk levels not in LOW/MEDIUM/HIGH/CRITICAL should not crash."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(risk_level="UNKNOWN"),  # type: ignore
        _make_cycle(risk_level="LOW"),
        _make_cycle(risk_level="CUSTOM"),  # type: ignore
        _make_cycle(risk_level="MEDIUM"),
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)
    # Should not crash — only known levels appear in output
    assert "RISK TREND:" in result
    assert "LOW: 1" in result
    assert "MEDIUM: 1" in result
    # Unknown levels are counted internally but not displayed
    # since the format loop only iterates over (LOW, MEDIUM, HIGH, CRITICAL)
    assert "UNKNOWN" not in result
    assert "CUSTOM" not in result


# ── Output contract: all sections present ─────────────────────────────────────

def test_full_output_contains_all_sections():
    """Verify that a fully-populated cycle produces all expected sections."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(
            fatigue=0.25,
            risk_level="MEDIUM",
            ideas=["Rotate 'X' from 'A' to 'B'", "Refresh 'X' hooks", "Expand visual diversity"],
            warnings=["Style overuse warning", "Platform health issue"],
            opportunity="VISUAL EXPANSION: 4 unused styles",
            experiment="Style A/B Test: 'New' vs current",
            duration_ms=450,
        )
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)

    required_sections = [
        "📈 *FATIGUE TREND:*",
        "🔴 *RISK TREND:*",
        "💡 *TOP IDEAS:*",
        "⚠️ *TOP WARNINGS:*",
        "🚀 *OPPORTUNITIES:*",
        "🎯 *EXPERIMENTS:*",
        "📊 *STATS:*",
    ]
    for section in required_sections:
        assert section in result, f"Missing section: {section}"


def test_output_uses_markdown_formatting():
    """Verify Markdown bold markers for Telegram rendering."""
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    cycles = [
        _make_cycle(
            fatigue=0.2,
            risk_level="MEDIUM",
            ideas=["Rotate 'X' from 'A' to 'B'"],
            warnings=["Style overuse warning"],
            opportunity="VISUAL EXPANSION: 4 unused styles",
            experiment="Style A/B Test: 'New' vs current",
        )
    ]
    result = HermesMetaOrchestrator.build_weekly_summary(cycles)

    assert "*FATIGUE TREND:*" in result
    assert "*RISK TREND:*" in result
    assert "*TOP IDEAS:*" in result
    assert "*TOP WARNINGS:*" in result
    assert "*OPPORTUNITIES:*" in result
    assert "*EXPERIMENTS:*" in result
    assert "*STATS:*" in result

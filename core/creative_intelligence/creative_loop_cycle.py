#!/usr/bin/env python3
"""
Creative Loop Cycle for HERMES Autonomous Brain v3.

This module implements the autonomous creative cycle that runs every 3 hours.
It is called by the AutonomousLoop._cycle_creative() method.

The cycle:
1. Loads creative signal state from all CI sources
2. Detects style fatigue, repetition, and underperformance
3. Generates 3 creative ideas, 2 warnings, 1 opportunity
4. Persists creative_signal_snapshot.json
5. Optionally triggers proactive Telegram notification (rate-limited)

Read-only advisory. Never mutates production pipeline.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from core.creative_intelligence.creative_signal_aggregator import (
    CreativeSignalSnapshot,
    aggregate_creative_signals,
)
from core.creative_intelligence.style_rotation_engine import (
    StyleRotationResult,
    recommend_style,
)
from core.creative_intelligence.signal_store import IMPERIO_ROOT, build_creative_signal_state


class CreativeCycleOutput:
    """Output of one creative cycle execution."""

    def __init__(
        self,
        snapshot: CreativeSignalSnapshot,
        rotation_results: list[StyleRotationResult],
        ideas: list[str],
        warnings: list[str],
        opportunity: str,
        risk: str,
    ):
        self.snapshot = snapshot
        self.rotation_results = rotation_results
        self.ideas = ideas
        self.warnings = warnings
        self.opportunity = opportunity
        self.risk = risk
        self.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

    def format_for_telegram(self) -> str:
        """Format output as a Telegram-friendly message."""
        lines = [
            "🧠 HERMES Creative Brain v3",
            "",
            "💡 3 IDEAS:",
        ]
        for idx, idea in enumerate(self.ideas[:3], 1):
            lines.append(f"  {idx}. {idea}")

        lines.append("")
        lines.append("⚠️ 2 WARNINGS:")
        for idx, warning in enumerate(self.warnings[:2], 1):
            lines.append(f"  {idx}. {warning}")

        lines.append("")
        lines.append(f"🚀 OPPORTUNITY: {self.opportunity}")
        lines.append(f"🔴 RISK: {self.risk}")

        if self.snapshot.global_style_fatigue > 0:
            lines.append("")
            lines.append("📊 STYLE ANALYSIS:")
            lines.append(f"  Global fatigue: {self.snapshot.global_style_fatigue:.2f}")
            if self.snapshot.most_overused_style:
                lines.append(
                    f"  Most overused: {self.snapshot.most_overused_style} "
                    f"({self.snapshot.most_overused_count} campaigns)"
                )
            if self.rotation_results:
                for rr in self.rotation_results[:3]:
                    lines.append(
                        f"  {rr.product_name}: {rr.current_style} → "
                        f"{rr.recommended_style} ({rr.fatigue_level})"
                    )

        lines.append("")
        lines.append("Mode: read-only advisory | No pipeline mutation")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "ideas": self.ideas,
            "warnings": self.warnings,
            "opportunity": self.opportunity,
            "risk": self.risk,
            "global_fatigue": self.snapshot.global_style_fatigue,
            "campaigns_with_repetition": self.snapshot.campaigns_with_repetition,
            "rotation_count": len(self.rotation_results),
            "mode": "advisory",
        }


def run_creative_cycle(
    root: Path = IMPERIO_ROOT,
    persist: bool = True,
) -> CreativeCycleOutput:
    """
    Execute one full creative intelligence cycle.

    This is the main function called by AutonomousLoop._cycle_creative().
    Returns CreativeCycleOutput with ideas, warnings, and opportunities.
    """
    root = Path(root)

    # 1. Aggregate all creative signals
    snapshot = aggregate_creative_signals(root=root, persist=persist)

    # 2. Run style rotation for campaigns with fatigue
    rotation_results: list[StyleRotationResult] = []
    for ps in snapshot.product_signals:
        if ps.style_fatigue_score > 0.2 or ps.is_underperforming:
            rr = recommend_style(ps.product_id, root=root)
            rotation_results.append(rr)

    # 3. Generate 3 creative ideas
    ideas = _generate_ideas(snapshot, rotation_results)

    # 4. Extract 2 warnings
    warnings = _extract_warnings(snapshot, rotation_results)

    # 5. Extract 1 opportunity
    opportunity = _extract_opportunity(snapshot)

    # 6. Extract 1 risk
    risk = _extract_risk(snapshot)

    output = CreativeCycleOutput(
        snapshot=snapshot,
        rotation_results=rotation_results,
        ideas=ideas,
        warnings=warnings,
        opportunity=opportunity,
        risk=risk,
    )

    # 7. Log cycle output
    if persist:
        _log_cycle_output(root, output)

    return output


def _generate_ideas(
    snapshot: CreativeSignalSnapshot,
    rotations: list[StyleRotationResult],
) -> list[str]:
    """Generate 3 creative ideas from snapshot data."""
    ideas: list[str] = []

    # Idea 1: Rotate most fatigued product
    critical = [r for r in rotations if r.fatigue_level in ("high", "critical")]
    if critical:
        rr = critical[0]
        ideas.append(
            f"{rr.product_name}: switch from '{rr.current_style}' to "
            f"'{rr.recommended_style}' ({rr.fatigue_level} fatigue, "
            f"{rr.consecutive_uses}x repetition)"
        )
    elif rotations:
        rr = rotations[0]
        ideas.append(
            f"{rr.product_name}: test '{rr.recommended_style}' "
            f"as visual refresh (currently '{rr.current_style}')"
        )
    else:
        ideas.append(
            "All campaigns show healthy style diversity — "
            "explore new visual archetype from style catalog"
        )

    # Idea 2: Refresh an underperforming campaign
    weak = [ps for ps in snapshot.product_signals if ps.is_underperforming]
    if weak:
        ps = weak[0]
        new_style = ps.recommended_styles[0] if ps.recommended_styles else "new visual approach"
        ideas.append(
            f"{ps.product_name}: underperforming (score {ps.performance_score:.0f}) "
            f"— try '{new_style}' + new hook angle"
        )
    else:
        top = snapshot.product_signals[0] if snapshot.product_signals else None
        if top:
            ideas.append(
                f"{top.product_name}: test contrarian hook against "
                f"current '{top.current_style}' style"
            )

    # Idea 3: Expand to untested category/style combination
    used_styles = set(ps.current_style for ps in snapshot.product_signals)
    unused = [s for s in snapshot.style_families if s not in used_styles]
    if unused:
        ideas.append(f"Test unused style family: '{unused[0]}' for next campaign launch")
    elif snapshot.available_styles > len(used_styles):
        ideas.append(
            f"Expand style diversity: {snapshot.available_styles} styles available, "
            f"only {len(used_styles)} in use"
        )
    else:
        ideas.append(
            "Create a Pinterest-style evergreen utility angle "
            "for the best-performing visual product"
        )

    # Ensure we have exactly 3 (max 3 iterations to prevent infinite loop)
    _safety = 0
    while len(ideas) < 3 and _safety < 10:
        _safety += 1
        defaults = [
            "Test one mood-driven variant (cinematic/dramatic) for top campaign",
            "Run a split-test: warm vs. cool palette on same product",
            "Explore external style fingerprint from CI trends",
        ]
        for d in defaults:
            if d not in ideas:
                ideas.append(d)
                break
        else:
            break  # All defaults already added, nothing left

    return ideas[:3]


def _extract_warnings(
    snapshot: CreativeSignalSnapshot,
    rotations: list[StyleRotationResult],
) -> list[str]:
    """Extract 2 most important warnings."""
    warnings: list[str] = []

    # Warning 1: Style overuse
    if snapshot.most_overused_count > 1:
        warnings.append(
            f"Style '{snapshot.most_overused_style}' overused "
            f"({snapshot.most_overused_count} campaigns — risk of visual fatigue)"
        )

    # Warning 2: Repetition or underperformance
    if snapshot.campaigns_with_repetition > 0:
        warnings.append(
            f"{snapshot.campaigns_with_repetition}/{snapshot.total_campaigns} "
            f"campaigns show style repetition"
        )
    elif snapshot.campaigns_underperforming > 0:
        warnings.append(
            f"{snapshot.campaigns_underperforming} campaigns underperforming "
            f"— creative refresh needed"
        )

    # Fallback warnings
    while len(warnings) < 2:
        if snapshot.global_style_fatigue > 0.3:
            warnings.append(
                f"Global style fatigue elevated ({snapshot.global_style_fatigue:.2f})"
            )
        else:
            warnings.append("No major creative repetition detected")
        break
    while len(warnings) < 2:
        warnings.append("Monitor engagement signals for creative fatigue indicators")

    return warnings[:2]


def _extract_opportunity(snapshot: CreativeSignalSnapshot) -> str:
    """Extract best opportunity from snapshot."""
    if snapshot.opportunities:
        first = snapshot.opportunities[0]
        if isinstance(first, dict):
            return str(first.get("detail", first.get("action", str(first))))
        return str(first)

    # Generate opportunity from available data
    unused_styles = snapshot.available_styles - len(
        set(ps.current_style for ps in snapshot.product_signals)
    )
    if unused_styles > 0:
        return f"{unused_styles} unused visual styles available for exploration"

    if snapshot.product_signals:
        top = max(snapshot.product_signals, key=lambda ps: ps.performance_score)
        return (
            f"Scale winning formula: {top.product_name} "
            f"(score {top.performance_score:.0f}) with new style variants"
        )

    return "No strong opportunity yet — keep collecting creative signals"


def _extract_risk(snapshot: CreativeSignalSnapshot) -> str:
    """Extract top creative risk."""
    if snapshot.risk_flags:
        first = snapshot.risk_flags[0]
        if isinstance(first, dict):
            detail = first.get("detail", str(first))
            severity = first.get("severity", "")
            return f"[{severity}] {detail}" if severity else str(detail)
        return str(first)

    if snapshot.campaigns_underperforming >= 3:
        return (
            f"{snapshot.campaigns_underperforming} campaigns underperforming "
            f"— systemic creative issue possible"
        )

    if snapshot.global_style_fatigue > 0.5:
        return f"High global style fatigue ({snapshot.global_style_fatigue:.2f})"

    return "No major creative risk detected"


def _log_cycle_output(root: Path, output: CreativeCycleOutput) -> None:
    """Append cycle output to creative_cycle_log.jsonl."""
    log_file = root / "logs" / "creative_cycle_log.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(output.to_dict(), default=str) + "\n")
    except Exception:
        pass

#!/usr/bin/env python3
"""
Proactive Brain — HERMES Creative Intelligence v3 central orchestrator.

The proactive brain is the single entry point for all proactive creative
intelligence. It coordinates:

- Creative signal aggregation
- Style rotation recommendations
- Autonomous creative cycles
- Telegram digest formatting
- Advisory style bias for Flow Director

All operations are READ-ONLY or WRITE-ONLY to CI state files.
Never mutates production pipeline, posting schedule, or campaign memory.

Feature flags control all optional integrations:
- FEATURE_CREATIVE_CYCLE: enable autonomous creative cycle
- FEATURE_STYLE_ROTATION: enable style rotation in flow director
- FEATURE_PROACTIVE_TELEGRAM: enable proactive Telegram notifications
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from core.creative_intelligence.creative_signal_aggregator import (
    CreativeSignalSnapshot,
    aggregate_creative_signals,
)
from core.creative_intelligence.creative_loop_cycle import (
    CreativeCycleOutput,
    run_creative_cycle,
)
from core.creative_intelligence.style_rotation_engine import (
    StyleRotationResult,
    recommend_style,
    recommend_style_for_category,
)
from core.creative_intelligence.signal_store import IMPERIO_ROOT


class ProactiveBrain:
    """
    Central proactive creative intelligence orchestrator.

    Usage:
        brain = ProactiveBrain()
        
        # Run a creative cycle (called by AutonomousLoop)
        output = brain.run_cycle()
        
        # Get style recommendation for a product
        rotation = brain.get_style_rotation("B001")
        
        # Format Telegram digest
        msg = brain.format_proactive_digest()
        
        # Get advisory style bias for Flow Director
        bias = brain.get_flow_director_style_bias("B001")
    """

    def __init__(self, root: Path = IMPERIO_ROOT):
        self._root = Path(root)
        self._last_cycle: CreativeCycleOutput | None = None
        self._last_cycle_ts: float = 0.0

        # Feature flags (read from env, default: shadow mode)
        self._feature_creative_cycle = (
            os.environ.get("FEATURE_CREATIVE_CYCLE", "1") == "1"
        )
        self._feature_style_rotation = (
            os.environ.get("FEATURE_STYLE_ROTATION", "0") == "1"
        )
        self._feature_proactive_telegram = (
            os.environ.get("FEATURE_PROACTIVE_TELEGRAM", "0") == "1"
        )

    # ── Core Operations ───────────────────────────────────────

    def run_cycle(self) -> CreativeCycleOutput:
        """Execute a full creative cycle. Safe to call frequently."""
        output = run_creative_cycle(root=self._root, persist=True)
        self._last_cycle = output
        self._last_cycle_ts = time.time()
        return output

    def get_snapshot(self, force_refresh: bool = False) -> CreativeSignalSnapshot:
        """Get current creative signal snapshot."""
        return aggregate_creative_signals(root=self._root, persist=not force_refresh)

    def get_style_rotation(self, product_id: str) -> StyleRotationResult:
        """Get style rotation recommendation for a product."""
        return recommend_style(product_id, root=self._root)

    def get_category_styles(self, category: str) -> list[str]:
        """Get all recommended styles for a category, least-used first."""
        return recommend_style_for_category(category, root=self._root)

    # ── Telegram Formatting ───────────────────────────────────

    def format_proactive_digest(self) -> str:
        """
        Format a proactive creative digest for Telegram.
        Uses cached cycle output if available (< 1h old), otherwise runs a new cycle.
        """
        output = self._last_cycle
        if (
            output is None
            or (time.time() - self._last_cycle_ts) > 3600
        ):
            output = self.run_cycle()
        return output.format_for_telegram()

    def format_product_diagnosis(self, product_id: str = "") -> str:
        """
        Explain creative scoring for a specific product.
        Falls back to top campaign if product_id is empty.
        """
        snapshot = self.get_snapshot(force_refresh=True)

        if product_id:
            ps = next(
                (s for s in snapshot.product_signals if s.product_id == product_id),
                None,
            )
        else:
            ps = snapshot.product_signals[0] if snapshot.product_signals else None

        if not ps:
            return "No campaign data available for creative diagnosis."

        rr = self.get_style_rotation(ps.product_id)

        lines = [
            f"🔍 Creative Diagnosis: {ps.product_name}",
            f"  Product ID: {ps.product_id}",
            f"  Category: {ps.category} | Phase: {ps.phase}",
            f"  Current style: {ps.current_style}",
            f"  Diversity score: {ps.diversity_score}",
            f"  Style fatigue: {ps.style_fatigue_score} ({ps.repetition_count}x repetition)",
            f"  Performance: {ps.performance_score:.0f}/100 ({ps.posts_count} posts)",
            f"  Underperforming: {'YES ⚠️' if ps.is_underperforming else 'no'}",
            "",
            f"🎨 Rotation: {rr.current_style} → {rr.recommended_style}",
            f"  Reason: {rr.reason}",
            f"  Fatigue: {rr.fatigue_level} | Alternatives: {', '.join(rr.alternatives[:3])}",
        ]

        if ps.risk_flags:
            lines.append(f"\n⚠️ Flags: {', '.join(ps.risk_flags)}")

        lines.append("\nMode: read-only advisory")
        return "\n".join(lines)

    def format_brand_creative_report(self) -> str:
        """Comprehensive brand + creative performance report."""
        snapshot = self.get_snapshot(force_refresh=True)

        lines = [
            "📊 HERMES Brand + Creative Report",
            "",
            "── Style Health ──",
            f"  Global fatigue: {snapshot.global_style_fatigue:.2f}",
            f"  Campaigns with repetition: {snapshot.campaigns_with_repetition}/{snapshot.total_campaigns}",
            f"  Underperforming: {snapshot.campaigns_underperforming}",
            f"  Available styles: {snapshot.available_styles}",
        ]

        if snapshot.most_overused_style:
            lines.append(
                f"  Top overused: {snapshot.most_overused_style} "
                f"({snapshot.most_overused_count}x)"
            )

        if snapshot.most_repeated_hook:
            lines.append(f"  Most repeated hook: '{snapshot.most_repeated_hook}'")

        lines.append("")
        lines.append("── Per-Product ──")
        for ps in snapshot.product_signals[:5]:
            fatigue_icon = (
                "🔴" if ps.style_fatigue_score > 0.5
                else "🟡" if ps.style_fatigue_score > 0.2
                else "🟢"
            )
            lines.append(
                f"  {fatigue_icon} {ps.product_name}: {ps.current_style} "
                f"(fatigue: {ps.style_fatigue_score:.2f}, score: {ps.performance_score:.0f})"
            )

        if snapshot.warnings:
            lines.append("")
            lines.append("── Warnings ──")
            for w in snapshot.warnings[:3]:
                lines.append(f"  ⚠️ {w}")

        if snapshot.opportunities:
            lines.append("")
            lines.append("── Opportunities ──")
            for o in snapshot.opportunities[:3]:
                detail = o.get("detail", str(o)) if isinstance(o, dict) else str(o)
                lines.append(f"  🚀 {detail}")

        lines.append("")
        lines.append("Mode: read-only advisory")
        return "\n".join(lines)

    # ── Flow Director Integration (Feature-Flagged) ───────────

    def get_flow_director_style_bias(self, product_id: str) -> dict | None:
        """
        Get optional style bias for Flow Director.
        
        Returns None if FEATURE_STYLE_ROTATION is disabled (safe default).
        When enabled, returns advisory style hints that flow_operator.py
        can optionally inject into Google Flow prompts.
        """
        if not self._feature_style_rotation:
            return None

        rr = self.get_style_rotation(product_id)
        return {
            "product_id": product_id,
            "recommended_style": rr.recommended_style,
            "fatigue_level": rr.fatigue_level,
            "reason": rr.reason,
            "mode": "advisory",
            "source": "creative_intelligence_v3",
        }

    def get_proactive_suggestions(self) -> list[dict]:
        """
        Generate proactive suggestions for Hermes to propose.
        These are NOT executed — they are suggestions the operator can act on.
        """
        snapshot = self.get_snapshot(force_refresh=True)
        suggestions: list[dict] = []

        # Suggestion 1: Rotate most fatigued product
        fatigued = sorted(
            snapshot.product_signals,
            key=lambda ps: -ps.style_fatigue_score,
        )
        if fatigued and fatigued[0].style_fatigue_score > 0.2:
            ps = fatigued[0]
            rr = self.get_style_rotation(ps.product_id)
            suggestions.append({
                "type": "style_rotation",
                "priority": "HIGH" if ps.style_fatigue_score > 0.5 else "MEDIUM",
                "product": ps.product_name,
                "action": f"Rotate '{ps.product_name}' from '{ps.current_style}' to '{rr.recommended_style}'",
                "reason": rr.reason,
            })

        # Suggestion 2: Refresh underperforming campaign
        weak = [ps for ps in snapshot.product_signals if ps.is_underperforming]
        if weak:
            ps = weak[0]
            suggestions.append({
                "type": "campaign_refresh",
                "priority": "HIGH",
                "product": ps.product_name,
                "action": f"Refresh hooks for '{ps.product_name}' (score {ps.performance_score:.0f})",
                "reason": f"Underperforming after {ps.posts_count} posts",
            })

        # Suggestion 3: Test new style family
        if snapshot.available_styles > 0:
            used = set(ps.current_style for ps in snapshot.product_signals)
            unused_count = snapshot.available_styles - len(used)
            if unused_count > 0:
                suggestions.append({
                    "type": "style_exploration",
                    "priority": "LOW",
                    "product": "next campaign",
                    "action": f"Test one of {unused_count} unused style families",
                    "reason": "Expand visual diversity for future campaigns",
                })

        # Suggestion 4: New campaign opportunity
        if snapshot.opportunities:
            opp = snapshot.opportunities[0]
            detail = opp.get("detail", str(opp)) if isinstance(opp, dict) else str(opp)
            suggestions.append({
                "type": "new_campaign",
                "priority": "MEDIUM",
                "product": "new",
                "action": detail,
                "reason": "External trend or CI opportunity detected",
            })

        return suggestions

    # ── Feature Flags ──────────────────────────────────────────

    @property
    def creative_cycle_enabled(self) -> bool:
        return self._feature_creative_cycle

    @property
    def style_rotation_enabled(self) -> bool:
        return self._feature_style_rotation

    @property
    def proactive_telegram_enabled(self) -> bool:
        return self._feature_proactive_telegram

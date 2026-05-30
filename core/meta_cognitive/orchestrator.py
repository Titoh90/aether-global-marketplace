#!/usr/bin/env python3
"""
HermesMetaOrchestrator — IMPERIO Unified Meta-Cognitive Brain.

The meta-cognitive orchestrator is the highest-level intelligence system in IMPERIO.
It unifies ALL signals (creative, performance, engagement, revenue, CI) into a
single cognitive state and generates proactive suggestions.

5-step cycle (every 4 hours):
  STEP 1 — System Snapshot: collect from all subsystems
  STEP 2 — Cognitive Synthesis: generate 4 state dimensions
  STEP 3 — Decision Generation: 3 ideas, 2 warnings, 1 opportunity, 1 experiment
  STEP 4 — Proactive Output Engine: Telegram-formatted insights
  STEP 5 — Memory Writeback: persist to meta_cognitive_log.json

All operations are READ-ONLY or ADDITIVE-ONLY:
- Never mutates production pipeline, posting schedule, or campaign memory
- Never executes actions automatically — only SUGGESTS
- Feature-flagged via FEATURE_META_COGNITIVE (default: disabled)
- All outputs logged to REVENUE/meta_cognitive_log.json

Architecture:
    HermesMetaOrchestrator
    ├── reads: ExecutiveTruthEngine (system snapshot)
    ├── reads: ProactiveBrain (creative intelligence)
    ├── reads: Engagement Engine (shadow data)
    ├── reads: Revenue Layer (revenue signals)
    ├── reads: Competitor Intelligence (CI trends)
    ├── reads: Campaign memory (REVENUE/campaigns.json)
    └── writes: REVENUE/meta_cognitive_log.json (ADDITIVE ONLY)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")


# ═══════════════════════════════════════════════════════════════════
# LLM Analysis — System Prompt (Hermes Meta Orchestrator v1)
# ═══════════════════════════════════════════════════════════════════

HERMES_META_SYSTEM_PROMPT = """\
You are Hermes Meta Orchestrator v1, the unified cognitive brain of the IMPERIO system.

You are NOT a chatbot. You are NOT a single agent. You are the coordination layer across ALL system intelligence.

Your job is to analyze the provided IMPERIO world state and produce a strategic narrative.

# DATA SOURCES YOU RECEIVE
- revenue_layer (clicks, conversions, affiliate data)
- engagement_engine (comments, replies, sentiment)
- core.creative_intelligence (style, diversity, briefs, inspiration)
- competitive_intelligence (trends, scraping, signals)
- operator layer (executors, failures, circuit breakers)
- system_readiness + risk_engine (health, stability)
- planning_engine (scheduled actions)

# CORE BEHAVIOR

## 1. ANALYZE WORLD STATE
Aggregate the provided data into:
- performance metrics
- creative diversity score
- campaign health
- executor health
- trending signals
- platform health

## 2. RUN 4 COGNITIVE CYCLES (in your analysis)

### CREATIVE CYCLE
- detect repetition in visual styles
- detect stale campaigns
- propose new styles inspired by external patterns
- suggest creative experiments (NOT execution)

### REVENUE CYCLE
- identify top-performing products
- detect underperforming campaigns
- suggest scaling or stopping actions

### RISK CYCLE
- check circuit breakers
- detect failing executors
- detect system instability
- recommend mitigation

### OPPORTUNITY CYCLE
- detect trending products
- detect viral content patterns
- suggest new campaigns or angles

## 3. DECISION OUTPUT FORMAT
Always output in this structure:

### INSIGHTS
- 3 key observations

### CREATIVE RECOMMENDATIONS
- 2 new content ideas

### RISKS
- system or performance risks

### OPPORTUNITIES
- trends or growth angles

### NEXT ACTIONS (SUGGESTED ONLY)
- never execute directly
- only recommend

## 4. TELEGRAM MODE
- be proactive
- do NOT wait for questions
- push insights if anomalies exist
- keep messages short and actionable
- use emoji sparingly for emphasis

## 5. RULES
- NEVER modify deterministic core
- NEVER execute publishing actions
- NEVER bypass circuit breakers
- ONLY suggest, never force actions
- Always prefer safety over automation
- Respond in Spanish (LatAm) — the user is a Spanish-speaking operator

## 6. GOAL
Transform IMPERIO from a reactive automation system into a proactive creative revenue intelligence system."""


# ═══════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CreativeState:
    """Creative health snapshot from CI + visual diversity engine."""
    global_style_fatigue: float = 0.0
    campaigns_with_repetition: int = 0
    total_campaigns: int = 0
    most_overused_style: str = ""
    most_overused_count: int = 0
    most_repeated_hook: str = ""
    available_styles: int = 0
    unused_styles: list[str] = field(default_factory=list)
    style_rotations_needed: list[dict] = field(default_factory=list)
    top_performing_style: str = ""
    worst_performing_style: str = ""


@dataclass
class PerformanceState:
    """Aggregated performance metrics from executive layer + revenue."""
    posts_today: int = 0
    posts_week: int = 0
    clicks_today: int = 0
    clicks_week: int = 0
    revenue_tracked: float = 0.0
    click_through_rate: float = 0.0
    top_product: str = ""
    worst_product: str = ""
    platform_health_avg: int = 100
    best_platform: str = ""
    worst_platform: str = ""
    health_score: int = 100


@dataclass
class OpportunityState:
    """Emerging opportunities from CI, trends, and underused resources."""
    trending_products: list[str] = field(default_factory=list)
    underexploited_angles: list[str] = field(default_factory=list)
    content_gaps: list[str] = field(default_factory=list)
    viral_opportunities: list[dict] = field(default_factory=list)
    unused_style_families: int = 0
    commercial_post_gap: bool = False
    educational_post_gap: bool = False


@dataclass
class RiskState:
    """Systemic risks requiring attention."""
    style_overuse_risk: str = ""
    engagement_decay: bool = False
    content_stagnation: bool = False
    revenue_drop: bool = False
    platform_risk: list[str] = field(default_factory=list)
    ai_spend_risk: bool = False
    guardrail_alerts: list[str] = field(default_factory=list)
    overall_risk_level: str = "LOW"  # LOW | MEDIUM | HIGH | CRITICAL


@dataclass
class MetaCognitiveState:
    """Unified cognitive state from all IMPERIO subsystems."""
    version: int = 1
    generated_at: str = ""
    mode: str = "advisory"
    cycle_id: str = ""

    creative: CreativeState = field(default_factory=CreativeState)
    performance: PerformanceState = field(default_factory=PerformanceState)
    opportunity: OpportunityState = field(default_factory=OpportunityState)
    risk: RiskState = field(default_factory=RiskState)

    # Synthesized decisions
    ideas: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    strategic_opportunity: str = ""
    recommended_experiment: str = ""


@dataclass
class MetaCognitiveOutput:
    """Output of one meta-cognitive cycle."""
    state: MetaCognitiveState
    timestamp: str
    cycle_duration_ms: int

    def format_for_telegram(self) -> str:
        """Format output as proactive Telegram message."""
        st = self.state
        lines = [
            "🧠 IMPERIO Meta-Cognitive Brain",
            f"   {st.generated_at}",
            "",
            "💡 PROACTIVE INSIGHT:",
        ]
        for idea in st.ideas[:3]:
            lines.append(f"  → {idea}")

        if st.warnings:
            lines.append("")
            lines.append("⚠️ WARNINGS:")
            for w in st.warnings[:2]:
                lines.append(f"  ⚠ {w}")

        lines.append("")
        lines.append(f"🚀 OPPORTUNITY: {st.strategic_opportunity}")
        lines.append(f"🎯 SUGGESTED EXPERIMENT: {st.recommended_experiment}")

        # System health
        lines.append("")
        lines.append("📊 SYSTEM STATE:")
        lines.append(f"  Health: {st.performance.health_score}/100")
        lines.append(f"  Posts today: {st.performance.posts_today}")
        lines.append(f"  Clicks today: {st.performance.clicks_today}")
        if st.performance.revenue_tracked > 0:
            lines.append(f"  Revenue tracked: ${st.performance.revenue_tracked:.2f}")

        lines.append("")
        lines.append(f"🎨 CREATIVE: Global fatigue {st.creative.global_style_fatigue:.2f}")
        if st.creative.style_rotations_needed:
            for rr in st.creative.style_rotations_needed[:2]:
                lines.append(
                    f"  {rr['product']}: {rr['current']} → {rr['recommended']} "
                    f"({rr['fatigue']})"
                )

        lines.append("")
        lines.append(f"🔴 RISK LEVEL: {st.risk.overall_risk_level}")
        if st.risk.platform_risk:
            lines.append(f"  Platform risk: {', '.join(st.risk.platform_risk)}")

        lines.append("")
        lines.append("Mode: read-only advisory | No automatic execution")
        return "\n".join(lines)

    def format_proactive_suggestions(self) -> str:
        """Format concise proactive suggestions (shorter Telegram message)."""
        st = self.state
        lines = [
            "💡 HERMES Proactive Suggestions",
            "",
            "🎯 SUGGESTED EXPERIMENT:",
            f"  {st.recommended_experiment}",
            "",
            "🚀 OPPORTUNITY:",
            f"  {st.strategic_opportunity}",
        ]
        if st.warnings:
            lines.append("")
            lines.append("⚠️ WARNINGS:")
            for w in st.warnings[:2]:
                lines.append(f"  ⚠ {w}")
        lines.append("")
        lines.append(f"Risk: {st.risk.overall_risk_level} | Fatigue: {st.creative.global_style_fatigue:.2f}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "cycle_duration_ms": self.cycle_duration_ms,
            "mode": "advisory",
            "version": self.state.version,
            "generated_at": self.state.generated_at,
            "cycle_id": self.state.cycle_id,
            "state": {
                "creative": {
                    "global_style_fatigue": self.state.creative.global_style_fatigue,
                    "campaigns_with_repetition": self.state.creative.campaigns_with_repetition,
                    "total_campaigns": self.state.creative.total_campaigns,
                    "most_overused_style": self.state.creative.most_overused_style,
                    "most_overused_count": self.state.creative.most_overused_count,
                    "most_repeated_hook": self.state.creative.most_repeated_hook,
                    "available_styles": self.state.creative.available_styles,
                    "unused_styles": self.state.creative.unused_styles,
                    "style_rotations_needed": self.state.creative.style_rotations_needed,
                    "top_performing_style": self.state.creative.top_performing_style,
                    "worst_performing_style": self.state.creative.worst_performing_style,
                },
                "performance": {
                    "posts_today": self.state.performance.posts_today,
                    "posts_week": self.state.performance.posts_week,
                    "clicks_today": self.state.performance.clicks_today,
                    "clicks_week": self.state.performance.clicks_week,
                    "revenue_tracked": self.state.performance.revenue_tracked,
                    "click_through_rate": self.state.performance.click_through_rate,
                    "top_product": self.state.performance.top_product,
                    "worst_product": self.state.performance.worst_product,
                    "platform_health_avg": self.state.performance.platform_health_avg,
                    "best_platform": self.state.performance.best_platform,
                    "worst_platform": self.state.performance.worst_platform,
                    "health_score": self.state.performance.health_score,
                },
                "opportunity": {
                    "trending_products": self.state.opportunity.trending_products[:5],
                    "underexploited_angles": self.state.opportunity.underexploited_angles[:3],
                    "content_gaps": self.state.opportunity.content_gaps,
                    "viral_opportunities": self.state.opportunity.viral_opportunities,
                    "unused_style_families": self.state.opportunity.unused_style_families,
                    "commercial_post_gap": self.state.opportunity.commercial_post_gap,
                    "educational_post_gap": self.state.opportunity.educational_post_gap,
                },
                "risk": {
                    "overall_risk_level": self.state.risk.overall_risk_level,
                    "style_overuse_risk": self.state.risk.style_overuse_risk,
                    "engagement_decay": self.state.risk.engagement_decay,
                    "content_stagnation": self.state.risk.content_stagnation,
                    "revenue_drop": self.state.risk.revenue_drop,
                    "platform_risk": self.state.risk.platform_risk,
                    "ai_spend_risk": self.state.risk.ai_spend_risk,
                    "guardrail_alerts": self.state.risk.guardrail_alerts,
                },
            },
            "decisions": {
                "ideas": self.state.ideas,
                "warnings": self.state.warnings,
                "strategic_opportunity": self.state.strategic_opportunity,
                "recommended_experiment": self.state.recommended_experiment,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MetaCognitiveOutput":
        """Reconstruct MetaCognitiveOutput from to_dict() output."""
        st = data.get("state", {})
        c = st.get("creative", {})
        p = st.get("performance", {})
        o = st.get("opportunity", {})
        r = st.get("risk", {})
        d = data.get("decisions", {})

        creative = CreativeState(
            global_style_fatigue=c.get("global_style_fatigue", 0.0),
            campaigns_with_repetition=c.get("campaigns_with_repetition", 0),
            total_campaigns=c.get("total_campaigns", 0),
            most_overused_style=c.get("most_overused_style", ""),
            most_overused_count=c.get("most_overused_count", 0),
            most_repeated_hook=c.get("most_repeated_hook", ""),
            available_styles=c.get("available_styles", 0),
            unused_styles=c.get("unused_styles", []),
            style_rotations_needed=c.get("style_rotations_needed", []),
            top_performing_style=c.get("top_performing_style", ""),
            worst_performing_style=c.get("worst_performing_style", ""),
        )

        performance = PerformanceState(
            posts_today=p.get("posts_today", 0),
            posts_week=p.get("posts_week", 0),
            clicks_today=p.get("clicks_today", 0),
            clicks_week=p.get("clicks_week", 0),
            revenue_tracked=p.get("revenue_tracked", 0.0),
            click_through_rate=p.get("click_through_rate", 0.0),
            top_product=p.get("top_product", ""),
            worst_product=p.get("worst_product", ""),
            platform_health_avg=p.get("platform_health_avg", 100),
            best_platform=p.get("best_platform", ""),
            worst_platform=p.get("worst_platform", ""),
            health_score=p.get("health_score", 100),
        )

        opportunity = OpportunityState(
            trending_products=o.get("trending_products", []),
            underexploited_angles=o.get("underexploited_angles", []),
            content_gaps=o.get("content_gaps", []),
            viral_opportunities=o.get("viral_opportunities", []),
            unused_style_families=o.get("unused_style_families", 0),
            commercial_post_gap=o.get("commercial_post_gap", False),
            educational_post_gap=o.get("educational_post_gap", False),
        )

        risk = RiskState(
            style_overuse_risk=r.get("style_overuse_risk", ""),
            engagement_decay=r.get("engagement_decay", False),
            content_stagnation=r.get("content_stagnation", False),
            revenue_drop=r.get("revenue_drop", False),
            platform_risk=r.get("platform_risk", []),
            ai_spend_risk=r.get("ai_spend_risk", False),
            guardrail_alerts=r.get("guardrail_alerts", []),
            overall_risk_level=r.get("overall_risk_level", "LOW"),
        )

        state = MetaCognitiveState(
            version=data.get("version", 1),
            generated_at=data.get("generated_at", ""),
            cycle_id=data.get("cycle_id", ""),
            creative=creative,
            performance=performance,
            opportunity=opportunity,
            risk=risk,
            ideas=d.get("ideas", []),
            warnings=d.get("warnings", []),
            strategic_opportunity=d.get("strategic_opportunity", ""),
            recommended_experiment=d.get("recommended_experiment", ""),
        )

        return cls(
            state=state,
            timestamp=data.get("timestamp", ""),
            cycle_duration_ms=data.get("cycle_duration_ms", 0),
        )


# ═══════════════════════════════════════════════════════════════════
# HermesMetaOrchestrator
# ═══════════════════════════════════════════════════════════════════

class HermesMetaOrchestrator:
    """
    Highest-level cognitive orchestrator in IMPERIO.

    Unifies all system signals into a single cognitive state and generates
    proactive, actionable suggestions. Runs every 4 hours via AutonomousLoop.

    Usage:
        orchestrator = HermesMetaOrchestrator()
        output = orchestrator.run_cycle()
        print(output.format_for_telegram())
    """

    def __init__(self, root: Path = IMPERIO_ROOT):
        self._root = Path(root)
        self._log_file = self._root / "REVENUE" / "meta_cognitive_log.json"

        # Feature flag
        self.enabled = os.environ.get("FEATURE_META_COGNITIVE", "0") == "1"

    # ── Core Cycle ──────────────────────────────────────────────

    def run_cycle(self, persist: bool = True) -> MetaCognitiveOutput:
        """
        Execute one complete meta-cognitive cycle.

        1. System Snapshot
        2. Cognitive Synthesis
        3. Decision Generation
        4. Proactive Output
        5. Memory Writeback
        """
        t0 = time.monotonic()
        cycle_id = time.strftime("%Y%m%d-%H%M%S")

        # ── STEP 1: System Snapshot ─────────────────────────────
        system = self._snapshot_system()
        creative = self._snapshot_creative()
        engagement = self._snapshot_engagement()
        revenue = self._snapshot_revenue()
        ci = self._snapshot_competitive_intelligence()

        # ── STEP 2: Cognitive Synthesis ─────────────────────────
        creative_state = self._synthesize_creative(creative, system)
        performance_state = self._synthesize_performance(system, revenue, engagement)
        opportunity_state = self._synthesize_opportunity(creative, ci, creative_state)
        risk_state = self._synthesize_risk(creative_state, performance_state, system)

        # ── STEP 3: Decision Generation ─────────────────────────
        ideas = self._generate_ideas(creative_state, opportunity_state)
        warnings = self._generate_warnings(creative_state, risk_state)
        strategic_opportunity = self._generate_strategic_opportunity(opportunity_state)
        recommended_experiment = self._generate_experiment(creative_state, opportunity_state)

        # Build unified state
        state = MetaCognitiveState(
            version=1,
            generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            cycle_id=cycle_id,
            creative=creative_state,
            performance=performance_state,
            opportunity=opportunity_state,
            risk=risk_state,
            ideas=ideas,
            warnings=warnings,
            strategic_opportunity=strategic_opportunity,
            recommended_experiment=recommended_experiment,
        )

        output = MetaCognitiveOutput(
            state=state,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            cycle_duration_ms=int((time.monotonic() - t0) * 1000),
        )

        # ── STEP 5: Memory Writeback ────────────────────────────
        if persist:
            self._writeback(output)

        return output

    # ════════════════════════════════════════════════════════════
    # STEP 1 — System Snapshot (read from all subsystems)
    # ════════════════════════════════════════════════════════════

    def _snapshot_system(self) -> dict:
        """Read complete system state from ExecutiveTruthEngine."""
        try:
            from executive_layer.executive_truth_engine import ExecutiveTruthEngine
            engine = ExecutiveTruthEngine()
            state = engine.state(force_refresh=True)
            return {
                "posts_today": state.posts_today,
                "posts_week": state.posts_week,
                "posts_total": state.posts_total,
                "clicks_today": state.clicks_today,
                "clicks_week": state.clicks_week,
                "clicks_total": state.clicks_total,
                "revenue_tracked": state.revenue_tracked,
                "active_campaigns": state.active_campaigns,
                "top_product": state.top_product,
                "top_product_asin": state.top_product_asin,
                "best_platform": state.top_platform,
                "worst_platform": state.worst_platform,
                "health_score": state.health_score,
                "failures_today": state.failures_today,
                "failures_week": state.failures_week,
                "ai_spend_today": state.ai_spend_today,
                "ai_budget": state.ai_budget,
                "ai_spend_pct": state.ai_spend_pct,
                "ssmie_mode": state.ssmie_mode,
                "ssmie_health": state.ssmie_health,
                "pipeline_status": state.pipeline_status,
                "platforms": [
                    {
                        "name": p.name,
                        "posts_today": p.posts_today,
                        "health_score": p.health_score,
                    }
                    for p in state.platforms
                ],
                "campaigns": [
                    {
                        "asin": c.asin,
                        "product_name": c.product_name,
                        "posts_count": c.posts_count,
                        "clicks": c.clicks,
                        "phase": c.phase,
                        "performance_score": c.performance_score,
                    }
                    for c in state.campaigns
                ],
            }
        except Exception:
            return {"error": "ExecutiveTruthEngine unavailable"}

    def _snapshot_creative(self) -> dict:
        """Read creative intelligence state from ProactiveBrain."""
        try:
            from core.creative_intelligence.proactive_brain import ProactiveBrain
            brain = ProactiveBrain()
            snapshot = brain.get_snapshot(force_refresh=True)
            return {
                "global_style_fatigue": snapshot.global_style_fatigue,
                "total_campaigns": snapshot.total_campaigns,
                "campaigns_with_repetition": snapshot.campaigns_with_repetition,
                "campaigns_underperforming": snapshot.campaigns_underperforming,
                "most_overused_style": snapshot.most_overused_style,
                "most_overused_count": snapshot.most_overused_count,
                "most_repeated_hook": snapshot.most_repeated_hook,
                "available_styles": snapshot.available_styles,
                "style_families": snapshot.style_families,
                "style_usage": snapshot.style_usage,
                "product_signals": [
                    {
                        "product_id": ps.product_id,
                        "product_name": ps.product_name,
                        "current_style": ps.current_style,
                        "style_fatigue_score": ps.style_fatigue_score,
                        "performance_score": ps.performance_score,
                        "posts_count": ps.posts_count,
                        "is_underperforming": ps.is_underperforming,
                        "recommended_styles": ps.recommended_styles,
                    }
                    for ps in snapshot.product_signals
                ],
                "warnings": snapshot.warnings,
                "opportunities": snapshot.opportunities,
            }
        except Exception:
            return {"error": "Creative intelligence unavailable"}

    def _snapshot_engagement(self) -> dict:
        """Read engagement shadow data."""
        try:
            shadow_log = self._root / "REVENUE" / "engagement_shadow_log.jsonl"
            entries = []
            if shadow_log.exists():
                try:
                    for line in shadow_log.read_text().splitlines()[-50:]:
                        if line.strip():
                            entries.append(json.loads(line))
                except Exception:
                    pass

            # Count intents
            intents = {}
            for e in entries:
                intent = e.get("intent", "unknown")
                intents[intent] = intents.get(intent, 0) + 1

            response_log = self._root / "engagement_engine" / "response_log.jsonl"
            response_count = 0
            if response_log.exists():
                try:
                    response_count = sum(1 for _ in response_log.read_text().splitlines() if _.strip())
                except Exception:
                    pass

            return {
                "entries_count": len(entries),
                "intents": intents,
                "recent_comments": [
                    {"username": e.get("username", ""), "intent": e.get("intent", ""),
                     "status": e.get("status", "")}
                    for e in entries[-5:]
                ],
                "total_responses": response_count,
            }
        except Exception:
            return {"error": "Engagement data unavailable"}

    def _snapshot_revenue(self) -> dict:
        """Read revenue signals."""
        try:
            from revenue_layer.revenue_ledger import compute_summary
            summary = compute_summary()
            return {
                "total_products": summary.get("total_products", 0),
                "total_conversions": summary.get("total_conversions", 0),
                "confirmed_revenue": summary.get("total_confirmed_revenue", 0.0),
                "pending_revenue": summary.get("total_pending_revenue", 0.0),
                "products": summary.get("products", []),
            }
        except Exception:
            # Fallback: read summary file
            summary_file = self._root / "logs" / "revenue" / "ledger" / "summary.json"
            if summary_file.exists():
                try:
                    return json.loads(summary_file.read_text())
                except Exception:
                    pass
            return {"error": "Revenue data unavailable"}

    def _snapshot_competitive_intelligence(self) -> dict:
        """Read competitive intelligence reports."""
        ci_dir = self._root / "memory" / "competitive_intelligence"
        try:
            reports = sorted(ci_dir.glob("ci_report_*.json"))
            latest = reports[-1] if reports else None
            if latest:
                return json.loads(latest.read_text())
        except Exception:
            pass
        return {"error": "CI data unavailable"}

    # ════════════════════════════════════════════════════════════
    # STEP 2 — Cognitive Synthesis
    # ════════════════════════════════════════════════════════════

    def _synthesize_creative(self, creative: dict, system: dict) -> CreativeState:
        """Synthesize creative health state."""
        state = CreativeState()
        state.global_style_fatigue = creative.get("global_style_fatigue", 0.0)
        state.campaigns_with_repetition = creative.get("campaigns_with_repetition", 0)
        state.total_campaigns = creative.get("total_campaigns", 0)
        state.most_overused_style = creative.get("most_overused_style", "")
        state.most_overused_count = creative.get("most_overused_count", 0)
        state.most_repeated_hook = creative.get("most_repeated_hook", "")
        state.available_styles = creative.get("available_styles", 0)

        # Compute unused styles
        used = set(
            ps.get("current_style", "")
            for ps in creative.get("product_signals", [])
        )
        all_styles = creative.get("style_families", [])
        state.unused_styles = [s for s in all_styles if s not in used][:5]

        # Rotations needed
        for ps in creative.get("product_signals", []):
            fatigue = ps.get("style_fatigue_score", 0)
            if fatigue > 0.2 or ps.get("is_underperforming"):
                rec = ps.get("recommended_styles", [])
                state.style_rotations_needed.append({
                    "product": ps.get("product_name", "")[:40],
                    "current": ps.get("current_style", ""),
                    "recommended": rec[0] if rec else "new style",
                    "fatigue": "high" if fatigue > 0.5 else "medium",
                    "score": ps.get("performance_score", 50),
                })

        # Top/worst performing styles
        style_scores: dict[str, list[float]] = {}
        for ps in creative.get("product_signals", []):
            style = ps.get("current_style", "")
            score = ps.get("performance_score", 50)
            if style not in style_scores:
                style_scores[style] = []
            style_scores[style].append(score)

        if style_scores:
            avg_by_style = {s: sum(sc) / len(sc) for s, sc in style_scores.items()}
            state.top_performing_style = max(avg_by_style, key=avg_by_style.get)
            state.worst_performing_style = min(avg_by_style, key=avg_by_style.get)

        return state

    def _synthesize_performance(
        self, system: dict, revenue: dict, engagement: dict
    ) -> PerformanceState:
        """Synthesize unified performance state."""
        state = PerformanceState()
        state.posts_today = system.get("posts_today", 0)
        state.posts_week = system.get("posts_week", 0)
        state.clicks_today = system.get("clicks_today", 0)
        state.clicks_week = system.get("clicks_week", 0)
        state.revenue_tracked = system.get("revenue_tracked", 0.0) or revenue.get("confirmed_revenue", 0.0)
        state.top_product = system.get("top_product", "")
        state.health_score = system.get("health_score", 100)

        # CTR
        if state.posts_today > 0:
            state.click_through_rate = state.clicks_today / state.posts_today

        # Best/worst platform
        platforms = system.get("platforms", [])
        if platforms:
            best = max(platforms, key=lambda p: p.get("health_score", 0))
            worst = min(platforms, key=lambda p: p.get("health_score", 0))
            state.best_platform = best.get("name", "")
            state.worst_platform = worst.get("name", "")

            avg_health = sum(p.get("health_score", 100) for p in platforms) / len(platforms)
            state.platform_health_avg = int(avg_health)

        # Find worst product (lowest posts/performance)
        campaigns = system.get("campaigns", [])
        if campaigns:
            worst = min(campaigns, key=lambda c: c.get("performance_score", 100))
            state.worst_product = worst.get("product_name", "")

        return state

    def _synthesize_opportunity(
        self, creative: dict, ci: dict, creative_state: CreativeState
    ) -> OpportunityState:
        """Synthesize emerging opportunities."""
        state = OpportunityState()

        # Trending products from CI
        ci_products = ci.get("products", ci.get("trends", []))
        if isinstance(ci_products, list):
            state.trending_products = [
                p.get("name", p.get("title", str(p)))[:60]
                for p in ci_products[:5]
            ]

        # Underexploited angles
        state.underexploited_angles = creative_state.unused_styles[:3]
        state.unused_style_families = len(creative_state.unused_styles)

        # Content gaps
        warnings = creative.get("warnings", [])
        opportunities = creative.get("opportunities", [])
        for opp in opportunities:
            detail = opp.get("detail", "") if isinstance(opp, dict) else str(opp)
            if detail and detail not in state.content_gaps:
                state.content_gaps.append(detail[:100])

        # Viral opportunities from CI
        if isinstance(ci_products, list):
            for p in ci_products[:3]:
                score = p.get("final_score", p.get("viral_score", 0))
                name = p.get("name", p.get("title", ""))[:50]
                if score > 5:
                    state.viral_opportunities.append({"product": name, "score": score})

        # Content mix gaps
        for opp in opportunities:
            detail = opp.get("detail", "") if isinstance(opp, dict) else str(opp)
            if "commercial" in detail.lower():
                state.commercial_post_gap = True
            if "educativo" in detail.lower() or "educational" in detail.lower():
                state.educational_post_gap = True

        return state

    def _synthesize_risk(
        self, creative: CreativeState, performance: PerformanceState, system: dict
    ) -> RiskState:
        """Synthesize risk assessment."""
        state = RiskState()
        risk_score = 0

        # Style overuse
        if creative.most_overused_count >= 3:
            state.style_overuse_risk = (
                f"Style '{creative.most_overused_style}' overused "
                f"({creative.most_overused_count} campaigns) — visual fatigue risk"
            )
            risk_score += 2
        elif creative.most_overused_count >= 2:
            state.style_overuse_risk = (
                f"Style '{creative.most_overused_style}' trending toward overuse "
                f"({creative.most_overused_count} campaigns)"
            )
            risk_score += 1

        # Engagement decay
        if performance.clicks_today == 0 and performance.posts_today > 3:
            state.engagement_decay = True
            risk_score += 1

        # Content stagnation
        if creative.global_style_fatigue > 0.5:
            state.content_stagnation = True
            risk_score += 2
        elif creative.global_style_fatigue > 0.3:
            risk_score += 1

        # Revenue drop
        if performance.revenue_tracked == 0 and performance.clicks_today > 0:
            state.revenue_drop = True
            risk_score += 1

        # Platform risk
        platforms = system.get("platforms", [])
        for p in platforms:
            if p.get("health_score", 100) < 60:
                state.platform_risk.append(
                    f"{p.get('name', '')}: health {p.get('health_score', 0)}/100"
                )
        if state.platform_risk:
            risk_score += len(state.platform_risk)

        # AI spend risk
        ai_spend_pct = system.get("ai_spend_pct", 0)
        if ai_spend_pct > 80:
            state.ai_spend_risk = True
            risk_score += 2

        # Guardrail alerts
        if system.get("ssmie_mode") == "PROTECTIVE":
            state.guardrail_alerts.append("SSMIE in PROTECTIVE mode — reduced operations")
            risk_score += 2

        # Determine overall level
        if risk_score >= 6:
            state.overall_risk_level = "CRITICAL"
        elif risk_score >= 4:
            state.overall_risk_level = "HIGH"
        elif risk_score >= 2:
            state.overall_risk_level = "MEDIUM"
        else:
            state.overall_risk_level = "LOW"

        return state

    # ════════════════════════════════════════════════════════════
    # STEP 3 — Decision Generation
    # ════════════════════════════════════════════════════════════

    def _generate_ideas(
        self, creative: CreativeState, opportunity: OpportunityState
    ) -> list[str]:
        """Generate 3 creative ideas."""
        ideas: list[str] = []

        # Idea 1: Style rotation for most fatigued product
        if creative.style_rotations_needed:
            rr = creative.style_rotations_needed[0]
            ideas.append(
                f"Rotate '{rr['product']}' from '{rr['current']}' "
                f"to '{rr['recommended']}' ({rr['fatigue']} fatigue)"
            )
        elif creative.unused_styles:
            ideas.append(
                f"Test unused style '{creative.unused_styles[0]}' "
                f"for next campaign launch"
            )

        # Idea 2: Performance improvement
        if creative.style_rotations_needed and len(creative.style_rotations_needed) > 1:
            rr = creative.style_rotations_needed[1]
            ideas.append(
                f"Refresh '{rr['product']}' creative hooks "
                f"(score {rr['score']:.0f}/100)"
            )
        elif opportunity.viral_opportunities:
            vo = opportunity.viral_opportunities[0]
            ideas.append(f"Capitalize on trending product: '{vo['product']}'")

        # Idea 3: Strategic expansion
        if opportunity.unused_style_families > 1:
            ideas.append(
                f"Expand visual diversity: {opportunity.unused_style_families} "
                f"unused styles available"
            )
        elif opportunity.commercial_post_gap:
            ideas.append("Fill content gap: add commercial/CTA post variant")
        elif opportunity.educational_post_gap:
            ideas.append("Fill content gap: add educational/utility post")
        else:
            ideas.append(
                "Run an A/B split test: warm vs cool palette "
                "on top-performing product"
            )

        # Ensure we have 3
        defaults = [
            "Test one mood-driven variant (cinematic/dramatic) for top campaign",
            "Explore external style fingerprint from CI trends",
            "Create a Pinterest-style evergreen angle for best visual product",
        ]
        for d in defaults:
            if len(ideas) >= 3:
                break
            if d not in ideas:
                ideas.append(d)

        return ideas[:3]

    def _generate_warnings(
        self, creative: CreativeState, risk: RiskState
    ) -> list[str]:
        """Generate 2 warnings."""
        warnings: list[str] = []

        if risk.style_overuse_risk:
            warnings.append(risk.style_overuse_risk)

        if risk.content_stagnation:
            warnings.append(
                f"Content stagnation: global style fatigue {creative.global_style_fatigue:.2f}"
            )

        if risk.platform_risk:
            warnings.append(f"Platform health issues: {'; '.join(risk.platform_risk[:2])}")

        while len(warnings) < 2:
            if creative.campaigns_with_repetition > 0:
                warnings.append(
                    f"{creative.campaigns_with_repetition}/{creative.total_campaigns} "
                    f"campaigns show style repetition"
                )
            else:
                warnings.append("All campaigns show healthy style diversity")
            break

        return warnings[:2]

    def _generate_strategic_opportunity(self, opportunity: OpportunityState) -> str:
        """Generate 1 strategic opportunity."""
        if opportunity.viral_opportunities:
            vo = opportunity.viral_opportunities[0]
            return f"TRENDING: '{vo['product']}' (viral score {vo['score']}) — create campaign now"

        if opportunity.unused_style_families >= 3:
            return (
                f"VISUAL EXPANSION: {opportunity.unused_style_families} unused "
                f"style families available — differentiate campaigns"
            )

        if opportunity.content_gaps:
            return opportunity.content_gaps[0]

        return "CONTENT DIVERSIFICATION: balance educational + commercial + lifestyle posts"

    def _generate_experiment(
        self, creative: CreativeState, opportunity: OpportunityState
    ) -> str:
        """Generate 1 recommended experiment."""
        # Experiment: style A/B test
        if creative.unused_styles:
            return (
                f"Style A/B Test: run '{creative.unused_styles[0]}' vs current "
                f"style on one product — measure CTR difference"
            )

        # Experiment: viral hook
        if opportunity.viral_opportunities:
            vo = opportunity.viral_opportunities[0]
            return f"Viral Hook Test: create 2 variants for '{vo['product']}' — contrarian vs aspiration"

        # Experiment: cross-platform
        return "Platform Test: repurpose top IG post for Pinterest/TikTok with platform-native edits"

    # ════════════════════════════════════════════════════════════
    # STEP 5 — Memory Writeback
    # ════════════════════════════════════════════════════════════

    def _writeback(self, output: MetaCognitiveOutput) -> None:
        """Persist to REVENUE/meta_cognitive_log.json (ADDITIVE append)."""
        try:
            self._log_file.parent.mkdir(parents=True, exist_ok=True)

            # Load existing log
            existing: list[dict] = []
            if self._log_file.exists():
                try:
                    existing = json.loads(self._log_file.read_text())
                    if not isinstance(existing, list):
                        existing = []
                except Exception:
                    existing = []

            # Append new cycle
            existing.append(output.to_dict())

            # Keep last 100 cycles
            self._log_file.write_text(
                json.dumps(existing[-100:], indent=2, default=str)
            )
        except Exception:
            pass

    # ── Read last cycle ─────────────────────────────────────────

    def last_cycle(self) -> MetaCognitiveOutput | None:
        """Read the most recent cycle from log."""
        try:
            if not self._log_file.exists():
                return None
            data = json.loads(self._log_file.read_text())
            if isinstance(data, list) and data:
                return MetaCognitiveOutput.from_dict(data[-1])
        except Exception:
            pass
        return None

    # ── Formatting helpers ──────────────────────────────────────

    def format_meta_state(self, output: MetaCognitiveOutput | None = None) -> str:
        """Format full cognitive state for /meta command."""
        if output is None:
            output = self.last_cycle()
        if output is None:
            return "No meta-cognitive cycle data available. Run a cycle first."

        return output.format_for_telegram()

    def format_proactive(self, output: MetaCognitiveOutput | None = None) -> str:
        """Format proactive suggestions for /proactive command."""
        if output is None:
            output = self.last_cycle()
        if output is None:
            return "No proactive suggestions available."

        return output.format_proactive_suggestions()

    @staticmethod
    def build_weekly_summary(cycles: list[dict]) -> str:
        """
        Build a formatted weekly summary from 7 days of meta-cognitive cycles.

        Shared logic used by both the autonomous loop (scheduled Monday 9am)
        and the /weekly Telegram command.
        """
        fatigue_vals = []
        risk_levels = []
        ideas_counts = {}
        warnings_counts = {}
        opportunities = {}
        experiments = {}
        durations = []

        for c in cycles:
            st = c.get("state", {})
            cr = st.get("creative", {})
            rk = st.get("risk", {})
            de = c.get("decisions", {})

            f = cr.get("global_style_fatigue")
            if f is not None:
                fatigue_vals.append(float(f))

            rl = rk.get("overall_risk_level", "")
            if rl:
                risk_levels.append(rl)

            for idea in de.get("ideas", []):
                key = HermesMetaOrchestrator._summarize_idea_theme(idea)
                ideas_counts[key] = ideas_counts.get(key, 0) + 1

            for w in de.get("warnings", []):
                key = w[:80]
                warnings_counts[key] = warnings_counts.get(key, 0) + 1

            opp = de.get("strategic_opportunity", "")
            if opp:
                key = opp[:80]
                opportunities[key] = opportunities.get(key, 0) + 1

            exp = de.get("recommended_experiment", "")
            if exp:
                key = exp[:80]
                experiments[key] = experiments.get(key, 0) + 1

            dur = c.get("cycle_duration_ms", 0)
            durations.append(dur)

        lines = []

        # Fatigue
        if fatigue_vals:
            first = fatigue_vals[0]
            last = fatigue_vals[-1]
            mn = min(fatigue_vals)
            mx = max(fatigue_vals)
            avg = sum(fatigue_vals) / len(fatigue_vals)
            if last < first - 0.05:
                trend = "↓ IMPROVING"
            elif last > first + 0.05:
                trend = "↑ WORSENING"
            else:
                trend = "→ STABLE"
            lines.append("📈 *FATIGUE TREND:*")
            lines.append(f"  Start: {first:.2%} → End: {last:.2%} | Range: {mn:.2%}–{mx:.2%}")
            lines.append(f"  Trend: {trend} | Avg: {avg:.2%}")
        else:
            lines.append("📈 *FATIGUE:* No data")
        lines.append("")

        # Risk
        if risk_levels:
            rcounts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
            for rl in risk_levels:
                rcounts[rl] = rcounts.get(rl, 0) + 1
            mid = len(risk_levels) // 2 or 1
            early = sum(1 for r in risk_levels[:mid] if r in ("HIGH", "CRITICAL"))
            late = sum(1 for r in risk_levels[-mid:] if r in ("HIGH", "CRITICAL"))
            if late < early:
                rtrend = "↓ IMPROVING"
            elif late > early:
                rtrend = "↑ WORSENING"
            else:
                rtrend = "→ STABLE"
            lines.append("🔴 *RISK TREND:*")
            parts = [f"{lvl}: {rcounts[lvl]}" for lvl in ("LOW", "MEDIUM", "HIGH", "CRITICAL") if rcounts[lvl] > 0]
            lines.append(f"  {', '.join(parts)}")
            lines.append(f"  Trend: {rtrend}")
        else:
            lines.append("🔴 *RISK:* No data")
        lines.append("")

        # Ideas
        if ideas_counts:
            top = sorted(ideas_counts.items(), key=lambda x: -x[1])[:4]
            lines.append("💡 *TOP IDEAS:*")
            for idea, cnt in top:
                lines.append(f"  • {idea} ({cnt}×)")
            lines.append(f"  Unique: {len(ideas_counts)}")
        else:
            lines.append("💡 *IDEAS:* No data")
        lines.append("")

        # Warnings
        if warnings_counts:
            top = sorted(warnings_counts.items(), key=lambda x: -x[1])[:3]
            lines.append("⚠️ *TOP WARNINGS:*")
            for w, cnt in top:
                lines.append(f"  • {w} ({cnt}×)")
        else:
            lines.append("⚠️ *WARNINGS:* No data")
        lines.append("")

        # Opportunities
        if opportunities:
            top = sorted(opportunities.items(), key=lambda x: -x[1])[:2]
            lines.append("🚀 *OPPORTUNITIES:*")
            for opp, cnt in top:
                lines.append(f"  • {opp} ({cnt}×)")

        # Experiments
        if experiments:
            top = sorted(experiments.items(), key=lambda x: -x[1])[:2]
            lines.append("")
            lines.append("🎯 *EXPERIMENTS:*")
            for exp, cnt in top:
                lines.append(f"  • {exp} ({cnt}×)")

        # Stats
        lines.append("")
        lines.append("📊 *STATS:*")
        lines.append(f"  Cycles: {len(cycles)} | Avg: {sum(durations)//max(len(durations),1)}ms")
        lines.append(f"  Unique ideas: {len(ideas_counts)} | Warning types: {len(warnings_counts)}")

        return "\n".join(lines)

    # ── LLM-Enriched Analysis ───────────────────────────────────

    async def enrich_with_llm(
        self, output: MetaCognitiveOutput | None = None
    ) -> str:
        """
        Enrich deterministic meta-cognitive state with LLM narrative analysis.

        Runs a fresh cycle if no output provided, then sends the structured
        state to Ollama/OpenRouter with the Hermes Meta Orchestrator system
        prompt for qualitative narrative enrichment.

        Feature-flagged via FEATURE_LLM_ANALYSIS (default: disabled).
        """
        if output is None:
            output = self.last_cycle()
        if output is None:
            return "No meta-cognitive data available. Run a cycle first."

        state_dict = output.to_dict()
        context = json.dumps(state_dict, indent=2, default=str)

        # Truncate if too long (Ollama context window ~2K tokens)
        if len(context) > 6000:
            context = context[:6000] + "\n... [truncated]"

        prompt = (
            f"Based on the following IMPERIO system state, produce your "
            f"strategic analysis:\n\n{context}\n\n"
            f"Follow your system instructions. Output in the decision format: "
            f"INSIGHTS, CREATIVE RECOMMENDATIONS, RISKS, OPPORTUNITIES, "
            f"NEXT ACTIONS."
        )

        try:
            from executive_layer.llm_reasoning import reason

            analysis = await reason(
                prompt=prompt,
                system_prompt=HERMES_META_SYSTEM_PROMPT,
                max_tokens=800,
                temperature=0.4,
            )

            header = (
                f"🧠 *ANÁLISIS LLM — Hermes Meta Orchestrator*\n"
                f"   {output.state.generated_at}\n"
                f"   Riesgo: {output.state.risk.overall_risk_level} | "
                f"Fatiga creativa: {output.state.creative.global_style_fatigue:.2f}\n"
                f"{'─' * 35}\n\n"
            )
            return header + analysis.strip()

        except ImportError:
            return (
                "⚠️ LLM reasoning module unavailable.\n\n"
                + output.format_for_telegram()
            )
        except Exception as e:
            return (
                f"⚠️ LLM analysis falló: {e}\n\n"
                + output.format_for_telegram()
            )

    @staticmethod
    def _summarize_idea_theme(idea: str) -> str:
        """Summarize a verbose creative idea into a short theme label."""
        il = idea.lower()
        if "rotate" in il or "rotation" in il:
            return "Rotate styles"
        if "refresh" in il or "hook" in il:
            return "Refresh hooks"
        if "visual diversity" in il or "unused style" in il or "expand" in il:
            return "Expand visual diversity"
        if "a/b" in il or "split test" in il:
            return "Run A/B test"
        if "trending" in il or "capitalize" in il:
            return "Capitalize on trends"
        if "content gap" in il or "fill" in il:
            return "Fill content gaps"
        if "test" in il:
            return "Test new approach"
        return idea[:60] + ("..." if len(idea) > 60 else "")

    def format_why_creative(self, product_query: str = "") -> str:
        """Format creative explanation for /why creative command."""
        try:
            from core.creative_intelligence.proactive_brain import ProactiveBrain
            brain = ProactiveBrain()

            if product_query:
                return brain.format_product_diagnosis(product_query)

            return brain.format_brand_creative_report()
        except Exception as e:
            return f"Creative intelligence unavailable: {e}"

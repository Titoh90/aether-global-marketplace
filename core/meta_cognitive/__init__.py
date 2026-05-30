"""
meta_cognitive — IMPERIO Meta-Cognitive Orchestrator.

Unifies all IMPERIO system signals (creative, performance, engagement,
revenue, competitive intelligence) into a single cognitive state and
generates proactive, actionable suggestions.

All operations are READ-ONLY or ADDITIVE-ONLY:
- Never mutates production pipeline
- Never executes actions automatically — only SUGGESTS
- Feature-flagged via FEATURE_META_COGNITIVE

Architecture:
    HermesMetaOrchestrator
    ├── reads: ExecutiveTruthEngine (system snapshot)
    ├── reads: ProactiveBrain (creative intelligence)
    ├── reads: Engagement Engine (shadow data)
    ├── reads: Revenue Layer (revenue signals)
    └── writes: REVENUE/meta_cognitive_log.json
"""

from core.meta_cognitive.orchestrator import (
    HermesMetaOrchestrator,
    MetaCognitiveState,
    MetaCognitiveOutput,
    CreativeState,
    PerformanceState,
    OpportunityState,
    RiskState,
)

__all__ = [
    "HermesMetaOrchestrator",
    "MetaCognitiveState",
    "MetaCognitiveOutput",
    "CreativeState",
    "PerformanceState",
    "OpportunityState",
    "RiskState",
]

#!/usr/bin/env python3
"""
core — IMPERIO Core Systems

Layers:
    knowledge_core      — Semantic memory & persistence
    llm                 — LLM provider abstraction
    inference_dispatch  — Model routing & dispatch gate
    visual_intelligence — Archetype engine & visual optimization
    visual_truth        — Truth layer for visual assertions
    competitive_intelligence — CI layer (Phase 2): competitor analysis
    cinematic_video     — Cinematic Video Research Layer (Phase 3)
    engagement          — User engagement & comments
    flight_check        — Pre-deploy flight check gate (Phase 2+3)
"""

# Flight check — pre-deploy gate
from core.flight_check import (
    run_flight_check,
    get_latest_report,
    FlightCheckReport,
    SuiteResult,
)

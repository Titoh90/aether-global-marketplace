"""
creative_intelligence — HERMES Creative Brain v3.

Additive-only advisory layer. It reads existing IMPERIO signals and writes only
creative intelligence state/fingerprint files. It never posts, dispatches, or
mutates deterministic core systems.

v3 adds: proactive brain, autonomous creative cycle, style rotation engine,
and unified creative signal aggregation.
"""

from core.creative_intelligence.signal_store import build_creative_signal_state
from core.creative_intelligence.creative_brief_generator import generate_creative_brief
from core.creative_intelligence.visual_diversity_engine import score_visual_diversity
from core.creative_intelligence.creative_signal_aggregator import (
    CreativeSignalSnapshot,
    ProductCreativeSignal,
    aggregate_creative_signals,
)
from core.creative_intelligence.style_rotation_engine import (
    StyleRotationResult,
    recommend_style,
    recommend_style_for_category,
)
from core.creative_intelligence.creative_loop_cycle import (
    CreativeCycleOutput,
    run_creative_cycle,
)
from core.creative_intelligence.proactive_brain import ProactiveBrain

__all__ = [
    # v2 (existing)
    "build_creative_signal_state",
    "generate_creative_brief",
    "score_visual_diversity",
    # v3 (new)
    "aggregate_creative_signals",
    "CreativeSignalSnapshot",
    "ProductCreativeSignal",
    "recommend_style",
    "recommend_style_for_category",
    "StyleRotationResult",
    "run_creative_cycle",
    "CreativeCycleOutput",
    "ProactiveBrain",
]

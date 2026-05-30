#!/usr/bin/env python3
"""
memory_logger.py — Persists engagement interactions to knowledge_core.

Non-blocking — uses persist_learning() from semantic_memory.
Every interaction is logged as a structured entry in the knowledge store.

Fuel for Revenue Layer (read-only) — feeds metrics but NEVER modifies pipelines.

Usage:
    from core.engagement.memory_logger import log_engagement

    log_engagement(record)
"""

from __future__ import annotations

import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.engagement.schemas import EngagementRecord

# Best-effort import — knowledge_core may not be available
try:
    from core.knowledge_core.semantic_memory import persist_learning
except ImportError:
    def persist_learning(content, memory_type, tags=None, source="auto"):
        pass


# ── Public API ────────────────────────────────────────────────────────────────

def log_engagement(record: EngagementRecord) -> None:
    """
    Persist a completed engagement interaction to the knowledge store.

    Persists:
        - comment_text + intent + response → "engagement" memory type
        - If intent was purchase_intent, also logs to "revenue" memory type
        - Tags include: platform, intent type, and whether response passed tone check

    Args:
        record: completed EngagementRecord from process_comment()

    Never raises. If knowledge_core is unavailable or persist fails, silently skips.
    """
    tags = [
        record.platform,
        record.intent.intent,
        "tone_passed" if record.response.passed_tone_check else "tone_failed",
        "affiliate" if record.comment.has_affiliate_link else "no_link",
    ]

    content = (
        f"ENGAGEMENT on {record.platform} | post={record.post_id} | intent={record.intent.intent}\n"
        f"COMMENT (@{record.comment.username}): {record.comment.comment_text}\n"
        f"RESPONSE: {record.response.response_text}\n"
        f"TONE: {'PASS' if record.response.passed_tone_check else 'FAIL — ' + ', '.join(record.response.tone_issues)}\n"
        f"TIMESTAMP: {record.posted_at}"
    )

    try:
        persist_learning(
            content=content,
            memory_type="engagement",
            tags=tags,
            source="engagement_layer",
        )
    except Exception:
        pass

    # Revenue signal: log purchase/price inquiries separately
    if record.intent.intent in ("purchase_intent", "price_inquiry"):
        revenue_content = (
            f"REVENUE SIGNAL from {record.platform}\n"
            f"POST: {record.post_id}\n"
            f"USER: @{record.comment.username}\n"
            f"INTENT: {record.intent.intent} (confidence: {record.intent.confidence:.1%})\n"
            f"RESPONSE SENT: {bool(record.response.response_text)}\n"
            f"CONVERSION: {'click' if record.conversion_click else 'none'}"
        )

        try:
            persist_learning(
                content=revenue_content,
                memory_type="revenue",
                tags=[
                    record.platform,
                    "engagement_signal",
                    record.intent.intent,
                ],
                source="engagement_layer",
            )
        except Exception:
            pass


def log_batch(records: list[EngagementRecord]) -> None:
    """Persist a batch of engagement records."""
    for record in records:
        log_engagement(record)

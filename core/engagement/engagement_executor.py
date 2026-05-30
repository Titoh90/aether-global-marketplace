#!/usr/bin/env python3
"""
engagement_executor.py — Orchestrates the full engagement pipeline.

Flow:
    COMMENT IN → comment_listener → intent_classifier → response_generator
              → tone_guard → engagement_executor → memory_logger

Usage:
    from core.engagement.engagement_executor import process_comment

    record = process_comment({
        "post_id": "post-abc",
        "comment_text": "Cuánto cuesta?",
        "platform": "Instagram",
        "username": "@buyer",
    })
    print(record.response.response_text)

Rules:
    - NEVER modifies: Flow operator, Truth Layer, Dispatch Gate, Revenue Layer
    - ONLY writes logs and reads affiliate links
    - NEVER calls providers directly (always through dispatch layer)
    - NEVER raises — always returns EngagementRecord
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.engagement.schemas import CommentEvent, EngagementRecord
from core.engagement.comment_listener import listen
from core.engagement.intent_classifier import classify_intent
from core.engagement.response_generator import generate_response
from core.engagement.tone_guard import validate, sanitize
from core.engagement.memory_logger import log_engagement


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ── Public API ────────────────────────────────────────────────────────────────

def process_comment(
    comment:            dict,
    has_affiliate_link: bool = False,
    auto_log:           bool = True,
) -> EngagementRecord:
    """
    Full engagement processing pipeline for a single comment.

    Pipeline:
        1. comment_listener — normalize and validate
        2. intent_classifier — classify intent (via dispatch, local fallback)
        3. response_generator — generate response (via dispatch, template fallback)
        4. tone_guard — validate response against rules
        5. memory_logger — persist interaction (if auto_log=True)

    Args:
        comment:            raw comment dict (post_id, comment_text, platform, username, ...)
        has_affiliate_link: whether parent post has tracked affiliate link
        auto_log:           whether to auto-persist to memory_logger

    Returns:
        EngagementRecord — never raises. Check .response.passed_tone_check
        and .response.response_text.
    """
    # ── Step 1: Listen ────────────────────────────────────────────────────────
    event = listen(comment)

    # Attach affiliate link flag
    if has_affiliate_link:
        event = CommentEvent(
            post_id=event.post_id,
            comment_text=event.comment_text,
            platform=event.platform,
            username=event.username,
            timestamp=event.timestamp,
            comment_id=event.comment_id,
            has_affiliate_link=True,
        )

    # ── Step 2: Classify intent ────────────────────────────────────────────
    intent = classify_intent(event)

    # ── Step 3: Generate response ──────────────────────────────────────────
    raw_response = generate_response(event, intent)

    # ── Step 4: Validate with tone guard ───────────────────────────────────
    sanitized_text = sanitize(raw_response.response_text)
    validated = validate(
        response_text=sanitized_text,
        intent=intent.intent,
        has_affiliate_link=event.has_affiliate_link,
    )

    # ── Step 5: Build record ───────────────────────────────────────────────
    record = EngagementRecord(
        comment=event,
        intent=intent,
        response=validated,
        posted_at=_now_iso(),
        post_id=event.post_id,
        platform=event.platform,
    )

    # ── Step 6: Log ────────────────────────────────────────────────────────
    if auto_log:
        log_engagement(record)

    return record


def process_batch(
    comments:           list[dict],
    has_affiliate_link: bool = False,
    auto_log:           bool = True,
) -> list[EngagementRecord]:
    """
    Process a batch of comments through the full pipeline.

    Args:
        comments:           list of raw comment dicts
        has_affiliate_link: whether parent post has tracked affiliate link
        auto_log:           whether to auto-persist each interaction

    Returns:
        List of EngagementRecords (same order as input).
    """
    return [process_comment(c, has_affiliate_link=has_affiliate_link, auto_log=auto_log) for c in comments]

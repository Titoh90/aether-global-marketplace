#!/usr/bin/env python3
"""
schemas.py — Frozen dataclasses for Engagement Layer.

All dataclasses are frozen=True — immutable after construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── Intent types ──────────────────────────────────────────────────────────────

INTENT_TYPES: frozenset[str] = frozenset({
    "price_inquiry",
    "purchase_intent",
    "curiosity",
    "comparison_request",
    "complaint",
    "spam",
    "support_request",
})


# ── Schemas ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CommentEvent:
    """
    Normalized comment received from a social platform.

    Fields:
        post_id:        post identifier this comment belongs to
        comment_text:   raw comment body
        platform:       source platform (instagram, tiktok, twitter, pinterest, etc.)
        username:       commenter handle
        timestamp:      ISO UTC timestamp of comment
        comment_id:     platform-specific comment ID (or generated)
        has_affiliate_link: whether the parent post has a tracked affiliate link
    """
    post_id:            str
    comment_text:       str
    platform:           str
    username:           str
    timestamp:          str
    comment_id:         str   = ""
    has_affiliate_link: bool  = False


@dataclass(frozen=True)
class IntentResult:
    """
    Classification result for a comment's intent.

    Fields:
        intent:       one of INTENT_TYPES
        confidence:   0.0-1.0 confidence score
        reasoning:    why this intent was chosen
        is_actionable: whether this comment should get a response
    """
    intent:        str
    confidence:    float
    reasoning:     str
    is_actionable: bool = True


@dataclass(frozen=True)
class ResponseResult:
    """
    Generated response with tone validation results.

    Fields:
        response_text:    the response to post (empty if blocked by tone guard)
        passed_tone_check: True if response passes all tone rules
        tone_issues:      list of violated rules (empty if passed)
        needs_affiliate:  True if response should include CTA/link
        was_generated:    True if inference was used (False if blocked or fallback)
    """
    response_text:     str
    passed_tone_check: bool
    tone_issues:       tuple[str, ...]  = ()
    needs_affiliate:   bool             = False
    was_generated:     bool             = False


@dataclass(frozen=True)
class EngagementRecord:
    """
    Complete engagement interaction — persisted to memory_logger.

    Fields:
        comment:        normalized comment event
        intent:         classified intent
        response:       generated (and tone-validated) response
        posted_at:      ISO UTC timestamp when response was posted
        conversion_click: whether a click was tracked (if available)
        post_id:        parent post identifier
        platform:       source platform
    """
    comment:          CommentEvent
    intent:           IntentResult
    response:         ResponseResult
    posted_at:        str
    conversion_click: bool = False
    post_id:          str  = ""
    platform:         str  = ""

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)

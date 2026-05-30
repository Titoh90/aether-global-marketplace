#!/usr/bin/env python3
"""
comment_listener.py — Receives and normalizes incoming comments from social platforms.

100% LOCAL — zero network calls, zero provider calls.
Normalizes platform names, validates required fields, and extracts post linkage.

Usage:
    from core.engagement.comment_listener import listen

    event = listen({
        "post_id": "post-abc123",
        "comment_text": "Cuánto cuesta este producto?",
        "platform": "Instagram",
        "username": "@curious_user",
        "comment_id": "ig_comment_456",
    })
"""

from __future__ import annotations

import datetime
import hashlib
import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.engagement.schemas import CommentEvent

# Platform name normalization map (lowercase → canonical)
_PLATFORM_MAP: dict[str, str] = {
    "ig":           "instagram",
    "instagram":    "instagram",
    "tiktok":       "tiktok",
    "tk":           "tiktok",
    "twitter":      "twitter",
    "x":            "twitter",
    "pin":          "pinterest",
    "pinterest":    "pinterest",
    "yt":           "youtube",
    "youtube":      "youtube",
    "fb":           "facebook",
    "facebook":     "facebook",
}

_REQUIRED_FIELDS = ("post_id", "comment_text", "platform")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _normalize_platform(platform: str) -> str:
    """Normalize platform name to canonical form. Unknown → lowercase as-is."""
    return _PLATFORM_MAP.get(platform.lower().strip(), platform.lower().strip())


def _validate_comment(comment: dict) -> list[str]:
    """Return list of missing or invalid fields."""
    issues = []
    for field in _REQUIRED_FIELDS:
        if field not in comment or not str(comment.get(field, "")).strip():
            issues.append(f"missing or empty field: {field}")
    return issues


def _generate_comment_id(comment: dict) -> str:
    """Generate deterministic comment_id from post_id + username + text hash."""
    raw = f"{comment.get('post_id','')}:{comment.get('username','')}:{comment.get('comment_text','')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


# ── Public API ────────────────────────────────────────────────────────────────

def listen(comment: dict) -> CommentEvent:
    """
    Normalize and validate an incoming comment from any social platform.

    Args:
        comment: raw dict from platform API or test input.
                 Required: post_id, comment_text, platform.
                 Optional: username, timestamp, comment_id, has_affiliate_link.

    Returns:
        CommentEvent — always returns an event; never raises.
        Caller should check .comment_text for empty string (validation failed).

    Never raises, never calls external services.
    """
    issues = _validate_comment(comment)
    if issues:
        return CommentEvent(
            post_id="",
            comment_text="",
            platform="unknown",
            username="",
            timestamp=_now_iso(),
            comment_id="",
            has_affiliate_link=False,
        )

    platform = _normalize_platform(str(comment.get("platform", "")))
    post_id  = str(comment.get("post_id", "")).strip()
    text     = str(comment.get("comment_text", "")).strip()
    username = str(comment.get("username", "")).strip()
    ts       = str(comment.get("timestamp", _now_iso()))
    cid      = str(comment.get("comment_id", "")).strip() or _generate_comment_id(comment)
    has_link = bool(comment.get("has_affiliate_link", False))

    return CommentEvent(
        post_id=post_id,
        comment_text=text,
        platform=platform,
        username=username,
        timestamp=ts,
        comment_id=cid,
        has_affiliate_link=has_link,
    )


def batch_listen(comments: list[dict]) -> list[CommentEvent]:
    """
    Process a batch of comments. Returns list of CommentEvents (including invalid ones).
    """
    return [listen(c) for c in comments]

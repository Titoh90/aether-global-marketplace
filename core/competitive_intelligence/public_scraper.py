#!/usr/bin/env python3
"""
public_scraper.py — Extracts STRUCTURAL PATTERNS from public social media data.

CRITICAL RULES:
- ONLY analyzes public data
- NEVER copies raw content (text, images, video)
- ONLY extracts structural fingerprints: hooks, CTAs, visual styles, metrics
- RATE-LIMITED: max 30 requests per hour across all accounts
- NO aggressive scraping — pauses between requests

Usage:
    from core.competitive_intelligence.public_scraper import fingerprint_account

    fingerprints = fingerprint_account(account, max_posts=50)
"""

from __future__ import annotations

import hashlib
import os
import sys
import threading
import time
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.competitive_intelligence.schemas import CompetitorAccount, PublicPostFingerprint
from core.competitive_intelligence._patterns import extract_hook_type, extract_cta_type

# Rate limiting — disabled in test mode via CI_TEST_MODE env var
_MAX_REQUESTS_PER_HOUR = 30
_REQUEST_INTERVAL_SECONDS = 3600 / _MAX_REQUESTS_PER_HOUR  # ~120s between requests
_SKIP_RATE_LIMIT = os.environ.get("CI_TEST_MODE", "") == "1"
_request_count = 0
_request_lock = threading.Lock()
_last_request_time = 0.0

# Simulated public data — when no live API is available, uses structured metadata
# In production: replace with platform API clients (Instagram Basic Display, TikTok Research API, etc.)
# NEVER scrape HTML — always use official APIs or public RSS/Atom feeds.


# ── Helpers ───────────────────────────────────────────────────────────────────

def _rate_limit() -> None:
    """Enforce rate limiting between requests. Skipped in test mode."""
    global _request_count, _last_request_time
    if _SKIP_RATE_LIMIT:
        return
    with _request_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < _REQUEST_INTERVAL_SECONDS and _last_request_time > 0:
            time.sleep(_REQUEST_INTERVAL_SECONDS - elapsed)
        _request_count += 1
        _last_request_time = time.monotonic()


def _make_fingerprint_id(account_id: str, index: int) -> str:
    raw = f"{account_id}:post:{index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ── Structural extraction (NO content copying) ────────────────────────────────

def _analyze_caption_structure(text: str) -> dict:
    """Extract structural metrics from caption — NEVER stores raw text."""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    sentences = []
    for line in lines:
        parts = [s.strip() for s in line.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        sentences.extend(parts)

    words = text.split()
    return {
        "sentence_count": len(sentences) if sentences else 1,
        "avg_sentence_length": len(words) / max(len(sentences), 1),
        "has_emoji": any(ord(c) > 127 for c in text),  # crude emoji detection
        "emoji_count": sum(1 for c in text if ord(c) > 127 and not c.isalpha()),
        "has_hashtags": "#" in text,
        "hashtag_count": text.count("#") if "#" in text else 0,
        "has_question": "?" in text,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def fingerprint_account(
    account:  CompetitorAccount,
    max_posts: int = 50,
) -> list[PublicPostFingerprint]:
    """
    Extract structural fingerprints from a competitor's public posts.

    This is a SIMULATION / STRUCTURAL ANALYZER — in production, connect to:
    - Instagram Basic Display API
    - TikTok Research API
    - Twitter API v2
    - Pinterest API

    For now: generates structural fingerprints from metadata patterns.
    These fingerprints train visual_intelligence and archetype_engine
    WITHOUT ever copying competitor content.

    Args:
        account:   CompetitorAccount from registry
        max_posts: max posts to fingerprint (capped at 50)

    Returns:
        List of PublicPostFingerprint — never raises, may be empty.
    """
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    fingerprints: list[PublicPostFingerprint] = []
    capped = min(max_posts, 50)

    # In test mode: generate varied dummy data so the CI→VI pipeline is testable
    # In production: returns empty fingerprints until real API is connected
    if _SKIP_RATE_LIMIT:
        _dummy_styles = ("luxury_dark", "warm_lifestyle", "tech_premium", "minimal_clean")
        _dummy_hooks = ("question_led", "hook_first", "storytelling", "shock_stat")
        _dummy_ctas = ("link_in_bio", "soft_mention", "direct_ask", "none")
        _dummy_palettes = ("dark_matte", "warm_golden", "cool_tech", "neutral_clean")
        _dummy_compositions = ("center_frame", "rule_of_thirds", "flat_lay", "negative_space")

        for i in range(capped):
            _rate_limit()
            fp_id = _make_fingerprint_id(account.account_id, i)

            # Cycle through dummy styles per post for variety
            style_idx = i % len(_dummy_styles)

            fp = PublicPostFingerprint(
                fingerprint_id=fp_id,
                account_id=account.account_id,
                platform=account.platform,
                collected_at=now,
                hook_type=_dummy_hooks[i % len(_dummy_hooks)],
                cta_type=_dummy_ctas[i % len(_dummy_ctas)],
                sentence_count=2 + (i % 3),
                avg_sentence_length=8.0 + (i % 10),
                has_emoji=i % 2 == 0,
                emoji_count=i % 3,
                has_hashtags=i % 2 == 1,
                hashtag_count=i % 4,
                has_question=i % 2 == 0,
                visual_style=_dummy_styles[style_idx],
                color_palette=_dummy_palettes[i % len(_dummy_palettes)],
                composition=_dummy_compositions[i % len(_dummy_compositions)],
                text_overlay=i % 2 == 0,
                likes_est=100 + (i * 50),
                comments_est=5 + (i % 10),
                shares_est=2 + (i % 5),
                views_est=1000 + (i * 200),
                engagement_rate=0.02 + (i * 0.005),
            )
            fingerprints.append(fp)

        return fingerprints

    for i in range(capped):
        _rate_limit()

        fp_id = _make_fingerprint_id(account.account_id, i)

        # In production: fetch real post metadata from platform API
        # For now: generate a structural fingerprint with reasonable defaults
        # The key point: we NEVER store raw content — only patterns

        fp = PublicPostFingerprint(
            fingerprint_id=fp_id,
            account_id=account.account_id,
            platform=account.platform,
            collected_at=now,
            hook_type="unknown",
            cta_type="none",
            sentence_count=1,
            avg_sentence_length=0.0,
            has_emoji=False,
            emoji_count=0,
            has_hashtags=False,
            hashtag_count=0,
            has_question=False,
            visual_style="unknown",
            color_palette="unknown",
            composition="unknown",
            text_overlay=False,
            likes_est=0,
            comments_est=0,
            shares_est=0,
            views_est=0,
            engagement_rate=0.0,
        )
        fingerprints.append(fp)

    return fingerprints


def fingerprint_raw_post(
    account:      CompetitorAccount,
    caption:      str,
    post_index:   int = 0,
    visual_style: str = "unknown",
    color_palette: str = "unknown",
    composition:  str = "unknown",
    text_overlay: bool = False,
    likes:        int = 0,
    comments:     int = 0,
    shares:       int = 0,
    views:        int = 0,
    follower_count: int = 0,
) -> PublicPostFingerprint:
    """
    Create a structural fingerprint from a SINGLE raw public post.
    Extracts ONLY patterns — NEVER stores raw content.

    Use this when you have real post data from a platform API or manual input.
    """
    import datetime

    struct = _analyze_caption_structure(caption)
    lines = [l.strip() for l in caption.strip().split("\n") if l.strip()]
    first2 = " ".join(lines[:2])
    last2 = " ".join(lines[-2:]) if len(lines) > 1 else caption
    hook = extract_hook_type(first2)
    cta = extract_cta_type(last2)

    eng_rate = 0.0
    if follower_count > 0:
        eng_rate = (likes + comments) / follower_count

    return PublicPostFingerprint(
        fingerprint_id=_make_fingerprint_id(account.account_id, post_index),
        account_id=account.account_id,
        platform=account.platform,
        collected_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        hook_type=hook,
        cta_type=cta,
        sentence_count=struct["sentence_count"],
        avg_sentence_length=struct["avg_sentence_length"],
        has_emoji=struct["has_emoji"],
        emoji_count=struct["emoji_count"],
        has_hashtags=struct["has_hashtags"],
        hashtag_count=struct["hashtag_count"],
        has_question=struct["has_question"],
        visual_style=visual_style,
        color_palette=color_palette,
        composition=composition,
        text_overlay=text_overlay,
        likes_est=likes,
        comments_est=comments,
        shares_est=shares,
        views_est=views,
        engagement_rate=round(eng_rate, 6),
    )

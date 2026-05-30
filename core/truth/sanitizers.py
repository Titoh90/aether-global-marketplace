#!/usr/bin/env python3
"""
sanitizers.py — Field-level sanitization functions for the Truth Layer.

Each function:
- Takes raw product dict
- Returns a typed, display-safe value
- NEVER fabricates, estimates, or hallucinates
- NEVER calls AI or external services
"""

from __future__ import annotations

from .validators import (
    is_valid_price,
    is_valid_rating,
    is_valid_reviews,
    is_valid_discount,
    is_valid_title,
    is_valid_url,
)


# ── Price ─────────────────────────────────────────────────────────────────────

PRICE_UNKNOWN_DISPLAY = "Check latest price on Amazon"


def sanitize_price(product: dict) -> tuple[str, float]:
    """
    Returns (price_display, numeric_price).

    Sources tried in order:
      product["price"] → product["current_price"] → product["sale_price"]

    If ALL sources invalid: price_display = PRICE_UNKNOWN_DISPLAY, numeric = 0.0
    NEVER estimates. NEVER uses fallback numeric values.
    """
    for key in ("price", "current_price", "sale_price"):
        raw = product.get(key)
        if raw is None:
            continue
        valid, numeric = is_valid_price(raw)
        if valid:
            return f"${numeric:.2f}", numeric

    return PRICE_UNKNOWN_DISPLAY, 0.0


# ── Rating ────────────────────────────────────────────────────────────────────

def sanitize_rating(product: dict) -> tuple[str, float]:
    """
    Returns (rating_display, numeric_rating).

    Sources: product["rating"] → product["avg_rating"] → product["star_rating"]

    If invalid: ("", 0.0). Never displays fabricated "4.5 stars" fallbacks.
    """
    for key in ("rating", "avg_rating", "star_rating"):
        raw = product.get(key)
        if raw is None:
            continue
        valid, numeric = is_valid_rating(raw)
        if valid:
            return f"{numeric}/5", numeric

    return "", 0.0


# ── Reviews ───────────────────────────────────────────────────────────────────

def sanitize_reviews(product: dict) -> tuple[str, int]:
    """
    Returns (reviews_display, numeric_reviews).

    Sources: product["reviews"] → product["review_count"] → product["ratings_total"]

    If invalid: ("", 0). Never hallucinates "thousands of reviews".
    """
    for key in ("reviews", "review_count", "ratings_total"):
        raw = product.get(key)
        if raw is None:
            continue
        valid, count = is_valid_reviews(raw)
        if valid:
            return f"{count:,} reviews", count

    return "", 0


# ── Discount ──────────────────────────────────────────────────────────────────

def sanitize_discount(product: dict, numeric_price: float) -> tuple[str, float]:
    """
    Returns (discount_display, discount_pct).

    Requires: numeric_price > 0 AND valid old_price from product.
    Sources: product["list_price"] → product["original_price"] → product["was_price"]

    If either missing/invalid: ("", 0.0). Never infers "50% off" without data.
    """
    if numeric_price <= 0:
        return "", 0.0

    for key in ("list_price", "original_price", "was_price"):
        raw = product.get(key)
        if raw is None:
            continue
        valid, old_numeric, pct = is_valid_discount(numeric_price, raw)
        if valid:
            savings = round(old_numeric - numeric_price, 2)
            return f"Save ${savings:.2f} ({pct:.0f}% off)", pct

    return "", 0.0


# ── Title ─────────────────────────────────────────────────────────────────────

_TITLE_MAX_LEN = 200


def sanitize_title(product: dict) -> str:
    """
    Returns clean title string, or "" if unrecoverable.

    Sources: product["name"] → product["title"] → product["product_name"]

    Cleans: unicode normalization, control chars, dangerous markdown, multi-spaces.
    Truncates at _TITLE_MAX_LEN characters.
    """
    for key in ("name", "title", "product_name"):
        raw = product.get(key)
        if raw is None:
            continue
        valid, cleaned = is_valid_title(raw)
        if valid:
            return cleaned[:_TITLE_MAX_LEN]

    return ""


# ── CTA (Call To Action) ──────────────────────────────────────────────────────

_CTA_TEMPLATES = {
    "has_price":      "Get it on Amazon — link in bio",
    "no_price":       "Check latest price on Amazon — link in bio",
    "check_price":    "Check latest price on Amazon",
    "link_in_bio":    "Link in bio",
    "default":        "Link in bio",
}


def sanitize_cta(product: dict, numeric_price: float, platform: str = "") -> str:
    """
    Returns a deterministic CTA string appropriate to data availability and platform.
    NEVER contains fabricated prices or false claims.
    """
    platform_lower = (platform or "").lower()

    # TikTok / Instagram: short form
    if platform_lower in ("tiktok", "instagram"):
        return _CTA_TEMPLATES["link_in_bio"]

    # Pinterest: slightly longer
    if platform_lower == "pinterest":
        if numeric_price > 0:
            return _CTA_TEMPLATES["has_price"]
        return _CTA_TEMPLATES["check_price"]

    # Generic
    if numeric_price > 0:
        return _CTA_TEMPLATES["has_price"]
    return _CTA_TEMPLATES["no_price"]


# ── Affiliate URL ─────────────────────────────────────────────────────────────

_DEFAULT_AFFILIATE_TAG = "aetherglobal-20"


def sanitize_affiliate_url(product: dict) -> str:
    """
    Returns verified affiliate URL string, or "" if unrecoverable.

    Sources: product["affiliate_url"] → product["aff_url"] →
             build from product["asin"] + default tag.
    """
    for key in ("affiliate_url", "aff_url"):
        raw = product.get(key)
        if raw is None:
            continue
        valid, url = is_valid_url(raw)
        if valid:
            return url

    # Try building from ASIN
    asin = str(product.get("asin") or "").strip()
    if asin and asin.isalnum() and len(asin) == 10:
        return f"https://www.amazon.com/dp/{asin}?tag={_DEFAULT_AFFILIATE_TAG}"

    return ""


# ── Image URL ─────────────────────────────────────────────────────────────────

def sanitize_image_url(product: dict) -> str:
    """
    Returns verified image URL, or "".
    Sources: product["image_url"] → product["image"] → product["main_image"]
    """
    for key in ("image_url", "image", "main_image"):
        raw = product.get(key)
        if raw is None:
            continue
        valid, url = is_valid_url(raw)
        if valid:
            return url
    return ""

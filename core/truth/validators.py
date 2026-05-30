#!/usr/bin/env python3
"""
validators.py — Deterministic field validators for the Truth Layer.

Rules:
- ZERO AI calls
- ZERO Claude/OpenAI prompts
- ZERO scoring
- Pure boolean / parse logic only
"""

from __future__ import annotations
import re
import unicodedata
from typing import Any


# ── Price ─────────────────────────────────────────────────────────────────────

# Characters allowed in a raw price string (digits, dot, comma, $, £, €, ¥, space)
_CURRENCY_STRIP = re.compile(r"[^\d.,]")
_MULTI_DOT      = re.compile(r"\.{2,}")
_MULTI_COMMA    = re.compile(r",{2,}")


def is_valid_price(value: Any) -> tuple[bool, float]:
    """
    Returns (is_valid, numeric_value).
    Valid: positive finite float parseable from value.
    Invalid: None, 0, negative, empty, non-numeric, NaN, inf.
    """
    if value is None:
        return False, 0.0

    raw = str(value).strip()
    if not raw:
        return False, 0.0

    # Reject explicitly negative values before stripping signs
    if raw.lstrip("$€£¥ ").startswith("-"):
        return False, 0.0

    # Reject scientific notation (e.g. "1e308", "2.5e10")
    if re.search(r"[eE][+\-]?\d", raw):
        return False, 0.0

    # Strip currency symbols and whitespace
    cleaned = _CURRENCY_STRIP.sub("", raw).strip()

    # Handle European format "29,99" → "29.99"
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    else:
        # Strip thousands separator commas e.g. "1,299.00"
        cleaned = cleaned.replace(",", "")

    if _MULTI_DOT.search(cleaned):
        return False, 0.0

    try:
        numeric = float(cleaned)
    except (ValueError, OverflowError):
        return False, 0.0

    if numeric != numeric:          # NaN check
        return False, 0.0
    if not (0 < numeric < 1_000_000):
        return False, 0.0

    return True, round(numeric, 2)


# ── Rating ────────────────────────────────────────────────────────────────────

def is_valid_rating(value: Any) -> tuple[bool, float]:
    """
    Returns (is_valid, numeric_value).
    Valid: float in range [1.0, 5.0].
    """
    if value is None:
        return False, 0.0

    raw = str(value).strip()
    if not raw:
        return False, 0.0

    # Strip "/5", " stars", etc.
    cleaned = re.sub(r"[^\d.]", "", raw)
    if not cleaned:
        return False, 0.0

    try:
        numeric = float(cleaned)
    except ValueError:
        return False, 0.0

    if not (1.0 <= numeric <= 5.0):
        return False, 0.0

    return True, round(numeric, 1)


# ── Reviews ───────────────────────────────────────────────────────────────────

def is_valid_reviews(value: Any) -> tuple[bool, int]:
    """
    Returns (is_valid, count).
    Valid: non-negative integer > 0.
    """
    if value is None:
        return False, 0

    raw = str(value).strip()
    if not raw:
        return False, 0

    # Strip commas, "reviews", "ratings", etc.
    cleaned = re.sub(r"[^\d]", "", raw)
    if not cleaned:
        return False, 0

    try:
        count = int(cleaned)
    except ValueError:
        return False, 0

    if count <= 0:
        return False, 0

    return True, count


# ── Discount ──────────────────────────────────────────────────────────────────

def is_valid_discount(price: float, old_price: Any) -> tuple[bool, float, float]:
    """
    Returns (is_valid, old_price_numeric, discount_pct).
    Requires both current price and old_price to be valid and old > new.
    """
    if price <= 0:
        return False, 0.0, 0.0

    valid_old, old_numeric = is_valid_price(old_price)
    if not valid_old:
        return False, 0.0, 0.0

    if old_numeric <= price:
        return False, 0.0, 0.0

    savings     = round(old_numeric - price, 2)
    discount_pct = round(savings / old_numeric * 100, 1)

    # Sanity: discount > 95% is almost certainly data error
    if discount_pct > 95:
        return False, 0.0, 0.0

    return True, old_numeric, discount_pct


# ── Title ─────────────────────────────────────────────────────────────────────

_DANGEROUS_MD   = re.compile(r"[*_`#\[\](){}<>|\\^~]")
_MULTI_SPACE    = re.compile(r" {2,}")
_CONTROL_CHARS  = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def is_valid_title(value: Any) -> tuple[bool, str]:
    """
    Returns (is_valid, cleaned_title).
    Valid: non-empty string after normalization.
    Cleans: unicode, control chars, dangerous markdown, duplicate spaces.
    """
    if value is None:
        return False, ""

    raw = str(value)

    # Normalize unicode to NFC (e.g., composed é vs combining e + ́)
    try:
        normalized = unicodedata.normalize("NFC", raw)
    except (TypeError, ValueError):
        normalized = raw

    # Remove control characters
    cleaned = _CONTROL_CHARS.sub(" ", normalized)

    # Remove dangerous markdown characters
    cleaned = _DANGEROUS_MD.sub("", cleaned)

    # Collapse multiple spaces
    cleaned = _MULTI_SPACE.sub(" ", cleaned).strip()

    if not cleaned:
        return False, ""

    return True, cleaned


# ── URL ───────────────────────────────────────────────────────────────────────

_URL_RE = re.compile(
    r"^https?://"
    r"(?:[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+)$"
)


def is_valid_url(value: Any) -> tuple[bool, str]:
    """Returns (is_valid, url_string). Simple structural check only."""
    if value is None:
        return False, ""
    raw = str(value).strip()
    if not raw:
        return False, ""
    if _URL_RE.match(raw):
        return True, raw
    return False, ""


# ── Availability ──────────────────────────────────────────────────────────────

_IN_STOCK_SIGNALS     = {"in stock", "in_stock", "available", "yes", "true", "1"}
_OUT_OF_STOCK_SIGNALS = {"out of stock", "out_of_stock", "unavailable", "no", "false", "0"}


def parse_availability(value: Any) -> str:
    """
    Returns "In Stock" | "Out of Stock" | "Check availability" | "".
    Never fabricates.
    """
    if value is None:
        return ""
    raw = str(value).strip().lower()
    if not raw:
        return ""
    if raw in _IN_STOCK_SIGNALS:
        return "In Stock"
    if raw in _OUT_OF_STOCK_SIGNALS:
        return "Out of Stock"
    return "Check availability"

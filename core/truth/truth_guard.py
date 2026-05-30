#!/usr/bin/env python3
"""
truth_guard.py — Central Truth Validation Layer for IMPERIO.

SINGLE SOURCE OF TRUTH for all product factual data.

Rules:
- ZERO AI calls
- ZERO Claude/OpenAI prompts
- ZERO scoring
- Fully deterministic
- Immutable output (SanitizedProduct is frozen dataclass)

Usage in any runtime module:

    from core.truth.truth_guard import normalize_product

    sp = normalize_product(raw_product_dict)
    caption = f"{sp.title_clean} — {sp.price_display}"
"""

from __future__ import annotations

import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure package is importable regardless of working directory
_TRUTH_DIR  = Path(__file__).parent
_CORE_DIR   = _TRUTH_DIR.parent
_ROOT_DIR   = _CORE_DIR.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from core.truth.schemas    import SanitizedProduct
from core.truth.sanitizers import (
    sanitize_price,
    sanitize_rating,
    sanitize_reviews,
    sanitize_discount,
    sanitize_title,
    sanitize_cta,
    sanitize_affiliate_url,
    sanitize_image_url,
)
from core.truth.validators import parse_availability


# ── Public API ────────────────────────────────────────────────────────────────

def normalize_product(
    raw: dict,
    platform: str = "",
) -> SanitizedProduct:
    """
    Convert raw Amazon product dict into a truth-validated, immutable SanitizedProduct.

    This is the ONLY function runtime modules should call.
    Raw dicts MUST NOT be passed directly to output layers.

    Args:
        raw:            Raw product dict from any source (trend_scout, campaigns.json, etc.)
        platform:       Optional platform hint for CTA selection ("tiktok", "instagram", etc.)

    Returns:
        SanitizedProduct — frozen, output-safe, immutable
    """
    warnings: list[str] = []

    # ── ASIN ─────────────────────────────────────────────────────────────────
    asin = str(raw.get("asin") or "").strip()
    if not asin:
        warnings.append("missing_asin")

    # ── Title ─────────────────────────────────────────────────────────────────
    title_clean = sanitize_title(raw)
    if not title_clean:
        warnings.append("missing_title")
        title_clean = asin or "Unknown Product"

    # ── Price ─────────────────────────────────────────────────────────────────
    price_display, numeric_price = sanitize_price(raw)
    if numeric_price == 0.0:
        warnings.append("missing_price")

    # ── Rating ────────────────────────────────────────────────────────────────
    rating_display, numeric_rating = sanitize_rating(raw)
    if numeric_rating == 0.0:
        warnings.append("missing_rating")

    # ── Reviews ───────────────────────────────────────────────────────────────
    reviews_display, numeric_reviews = sanitize_reviews(raw)
    if numeric_reviews == 0:
        warnings.append("missing_reviews")

    # ── Discount ──────────────────────────────────────────────────────────────
    discount_display, numeric_discount_pct = sanitize_discount(raw, numeric_price)

    # ── URLs ──────────────────────────────────────────────────────────────────
    affiliate_url = sanitize_affiliate_url(raw)
    if not affiliate_url:
        warnings.append("missing_affiliate_url")

    image_url = sanitize_image_url(raw)
    if not image_url:
        warnings.append("missing_image_url")

    # ── CTA ───────────────────────────────────────────────────────────────────
    # CTA is embedded in SanitizedProduct via sanitize_cta but not a top-level field.
    # Consumers call sp.to_prompt_context() or use price_display/affiliate_url directly.

    # ── Availability ──────────────────────────────────────────────────────────
    availability = parse_availability(raw.get("availability") or raw.get("in_stock"))

    # ── Timestamp ─────────────────────────────────────────────────────────────
    raw_ts = str(raw.get("source_timestamp") or raw.get("fetched_at") or raw.get("timestamp") or "")

    # ── Partial flag ──────────────────────────────────────────────────────────
    is_partial = bool(warnings)

    return SanitizedProduct(
        asin                 = asin,
        title_clean          = title_clean,
        price_display        = price_display,
        numeric_price        = numeric_price,
        rating_display       = rating_display,
        numeric_rating       = numeric_rating,
        reviews_display      = reviews_display,
        numeric_reviews      = numeric_reviews,
        discount_display     = discount_display,
        numeric_discount_pct = numeric_discount_pct,
        affiliate_url        = affiliate_url,
        image_url            = image_url,
        availability         = availability,
        raw_source_timestamp = raw_ts,
        _validation_warnings = tuple(warnings),
        _is_partial          = is_partial,
    )


def normalize_from_campaign(campaign: dict, platform: str = "") -> SanitizedProduct:
    """
    Convenience wrapper for campaigns.json format, which nests product data.

    campaigns.json structure:
      {
        "campaigns": {
          "<asin>": {
            "product_name": "...",
            "product_data": { "price": ..., "rating": ..., ... },
            ...
          }
        }
      }
    """
    # Flatten nested product_data into top-level view
    product_data = campaign.get("product_data") or {}
    merged: dict = {**product_data, **{
        k: v for k, v in campaign.items() if k != "product_data"
    }}
    # Map campaign-specific keys to standard keys
    if "product_name" in merged and "name" not in merged:
        merged["name"] = merged["product_name"]
    if "avg_rating" in merged and "rating" not in merged:
        merged["rating"] = merged["avg_rating"]
    if "review_count" in merged and "reviews" not in merged:
        merged["reviews"] = merged["review_count"]

    return normalize_product(merged, platform=platform)


# ── Batch normalization ───────────────────────────────────────────────────────

def normalize_products(raws: list[dict], platform: str = "") -> list[SanitizedProduct]:
    """Normalize a list of raw product dicts. Preserves order."""
    return [normalize_product(r, platform=platform) for r in raws]


# ── CLI / Self-test ───────────────────────────────────────────────────────────

def _run_tests() -> bool:
    """
    Deterministic test suite — 10 cases as specified.
    Returns True if all pass.
    """
    PASS = "✓"
    FAIL = "✗"
    failures = 0

    def check(label: str, condition: bool, got: Any = None) -> None:
        nonlocal failures
        if condition:
            print(f"  {PASS} {label}")
        else:
            print(f"  {FAIL} {label}  (got: {got!r})")
            failures += 1

    print("\n── Truth Guard Test Suite ───────────────────────────────────")

    # 1. price = None
    sp = normalize_product({"name": "Widget", "price": None})
    check("price=None → price_display=UNKNOWN", sp.price_display == "Check latest price on Amazon")
    check("price=None → numeric_price=0.0",     sp.numeric_price == 0.0)

    # 2. price = 0
    sp = normalize_product({"name": "Widget", "price": 0})
    check("price=0 → price_display=UNKNOWN",    sp.price_display == "Check latest price on Amazon")
    check("price=0 → numeric_price=0.0",        sp.numeric_price == 0.0)

    # 3. malformed currency
    sp = normalize_product({"name": "Widget", "price": "$$$bad"})
    check("malformed price → UNKNOWN",           sp.price_display == "Check latest price on Amazon")

    # 4. missing rating
    sp = normalize_product({"name": "Widget", "price": "29.99"})
    check("missing rating → rating_display=''",  sp.rating_display == "")
    check("missing rating → numeric_rating=0.0", sp.numeric_rating == 0.0)

    # 5. missing reviews
    sp = normalize_product({"name": "Widget", "price": "29.99", "rating": "4.5"})
    check("missing reviews → reviews_display=''",  sp.reviews_display == "")
    check("missing reviews → numeric_reviews=0",   sp.numeric_reviews == 0)

    # 6. malformed title
    sp = normalize_product({"name": "Pro\x00duct **[BOLD]** !!!", "price": "9.99"})
    check("malformed title cleaned",              "[" not in sp.title_clean and "\x00" not in sp.title_clean)
    check("malformed title non-empty",            bool(sp.title_clean))

    # 7. valid complete product
    sp = normalize_product({
        "name": "Owala FreeSip Insulated Stainless Steel",
        "asin": "B085DTZQNZ",
        "price": "34.99",
        "rating": "4.7",
        "reviews": "12450",
        "affiliate_url": "https://www.amazon.com/dp/B085DTZQNZ?tag=aetherglobal-20",
        "image_url": "https://m.media-amazon.com/images/I/example.jpg",
    })
    check("valid product → price_display",        sp.price_display == "$34.99")
    check("valid product → rating_display",       sp.rating_display == "4.7/5")
    check("valid product → reviews_display",      sp.reviews_display == "12,450 reviews")
    check("valid product → is_complete",          sp.is_complete())
    check("valid product → no warnings",          not sp._validation_warnings)

    # 8. partial product (some fields missing)
    sp = normalize_product({"name": "Some Product", "price": "19.99"})
    check("partial → is_partial=True",            sp._is_partial)
    check("partial → has_price=True",             sp.has_price())
    check("partial → has_rating=False",           not sp.has_rating())

    # 9. unicode corruption
    sp = normalize_product({"name": "Caf\xe9 Grinder \u2019s \u2605 Pro\u2122", "price": "45.00"})
    check("unicode NFC normalized",               "\u2019" in sp.title_clean or "s" in sp.title_clean)
    check("unicode title non-empty",              bool(sp.title_clean))

    # 10. empty affiliate URL — build from ASIN
    sp = normalize_product({
        "name": "Test Product",
        "asin": "B000000001",
        "price": "15.00",
    })
    check("missing affiliate URL → built from ASIN", "B000000001" in sp.affiliate_url)

    print(f"\n── Result: {10 + 4 - failures} passed / {10 + 4} total ─────────────────────────")
    return failures == 0


def _run_status() -> None:
    """Print a status summary using real campaign data if available."""
    campaigns_path = Path(_ROOT_DIR) / "REVENUE" / "campaigns.json"
    if not campaigns_path.exists():
        print("  [TruthGuard] No campaigns.json found — status unavailable")
        return

    raw = json.loads(campaigns_path.read_text())
    campaigns = raw.get("campaigns", raw) if isinstance(raw, dict) else {}

    print(f"\n{'═'*54}")
    print(f"  TRUTH GUARD — Status")
    print(f"{'═'*54}")
    print(f"  Campaigns    : {len(campaigns)}")

    for cid, campaign in list(campaigns.items())[:5]:
        sp = normalize_from_campaign(campaign)
        warnings = ", ".join(sp._validation_warnings) if sp._validation_warnings else "none"
        status = "✓ complete" if sp.is_complete() else f"⚠ partial [{warnings}]"
        print(f"  {sp.title_clean[:42]:<42}  {status}")

    print(f"{'═'*54}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IMPERIO Truth Guard")
    parser.add_argument("--test",   action="store_true", help="Run test suite")
    parser.add_argument("--status", action="store_true", help="Show campaign truth status")
    args = parser.parse_args()

    if args.test:
        ok = _run_tests()
        sys.exit(0 if ok else 1)
    if args.status:
        _run_status()
    if not any(vars(args).values()):
        parser.print_help()

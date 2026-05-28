"""
product_validator.py — Product Truth Layer enforcement.

## TWO-LAYER RULE

Layer 1: PRODUCT TRUTH LAYER
  - All product images MUST be from verified real sources (Amazon CDN)
  - No AI-generated images, renders, placeholders, or substitutions
  - If no real image can be sourced → product is EXCLUDED from hub
  - Enforced here via validate_product() and filter_products()

Layer 2: MARKETING LAYER (enforced separately in social posting pipeline)
  - AI-generated video ads, carousels, motion graphics → allowed
  - Stored in SurfaceProduct.marketing_video_url / marketing_carousel_urls
  - NEVER used for product display — social ads only

This module only governs Layer 1 (product truth).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

# ── Constants ────────────────────────────────────────────────────────────────

# Allowed domains for real product images (Amazon CDN + official merchant CDNs)
ALLOWED_IMAGE_DOMAINS: frozenset[str] = frozenset({
    "m.media-amazon.com",
    "images-na.ssl-images-amazon.com",
    "images-fe.ssl-images-amazon.com",
    "images-eu.ssl-images-amazon.com",
    "images.amazon.com",
})

# Valid ASIN format: exactly 10 alphanumeric characters
_ASIN_RE = re.compile(r'^[A-Z0-9]{10}$')

# Minimum price sanity check (free = suspicious, likely bad data)
_MIN_PRICE = 0.0


# ── Public API ────────────────────────────────────────────────────────────────

def validate_image_url(url: str) -> bool:
    """
    Return True if url is a real product image from an allowed domain.
    Empty string, placeholder URLs, and AI-generation endpoints all fail.
    """
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url.startswith("https://"):
        return False
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Strip port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        return domain in ALLOWED_IMAGE_DOMAINS
    except Exception:
        return False


def validate_asin(asin: str) -> bool:
    """Return True if asin is a valid Amazon ASIN (10 uppercase alphanumeric chars)."""
    if not asin or not isinstance(asin, str):
        return False
    return bool(_ASIN_RE.match(asin.strip().upper()))


def resolve_image_url(asin: str, image_url: str, size: str = "SL400") -> str:
    """
    Resolve the best real image URL for a product.

    Priority:
    1. Use image_url if it passes validate_image_url()
    2. Construct Amazon CDN URL from ASIN (m.media-amazon.com)
    3. Return "" if ASIN is invalid (product will be excluded)

    This function NEVER returns an AI-generated URL or placeholder.
    """
    if validate_image_url(image_url):
        return image_url
    if validate_asin(asin):
        return f"https://m.media-amazon.com/images/P/{asin}.01._{size}_.jpg"
    return ""


def validate_product(product: dict) -> tuple[bool, str]:
    """
    Validate a product dict against Product Truth Layer rules.

    Returns (is_valid: bool, reason: str).

    Exclusion criteria (any one fails the product):
    - Missing or invalid ASIN
    - No resolvable real image URL
    - Missing name
    - Missing affiliate_url
    """
    asin = product.get("asin", "") or ""
    if not validate_asin(asin):
        return False, f"invalid_asin:{asin!r}"

    name = product.get("name", "") or ""
    if not name.strip():
        return False, "missing_name"

    aff = product.get("affiliate_url", "") or ""
    if not aff.strip():
        return False, "missing_affiliate_url"

    # Image: must resolve to a real CDN URL
    raw_image = product.get("image_url", "") or ""
    resolved = resolve_image_url(asin, raw_image)
    if not resolved:
        return False, f"no_resolvable_image:asin={asin}"

    return True, "ok"


def filter_products(
    products: list[dict],
    log_exclusions: bool = True,
) -> list[dict]:
    """
    Filter a list of raw product dicts, keeping only those that pass
    Product Truth Layer validation.

    Also resolves image_url in-place (returns new dicts with resolved URL).
    Products with no real image are EXCLUDED — no substitution allowed.
    """
    valid: list[dict] = []
    for p in products:
        ok, reason = validate_product(p)
        if not ok:
            if log_exclusions:
                asin = p.get('asin', 'UNKNOWN')
                print(f"[product_validator] EXCLUDED {asin}: {reason}")
            continue

        # Resolve image_url to best real CDN URL
        asin = p["asin"]
        raw_image = p.get("image_url", "") or ""
        resolved_image = resolve_image_url(asin, raw_image)

        # Return new dict with resolved image (dicts are mutable, but we clone to be safe)
        p_resolved = dict(p)
        p_resolved["image_url"] = resolved_image
        valid.append(p_resolved)

    return valid


def validate_surface_product(p) -> tuple[bool, str]:
    """
    Validate an already-constructed SurfaceProduct against Product Truth Layer rules.
    Used as a final gate before rendering.
    """
    if not validate_asin(p.asin):
        return False, f"invalid_asin:{p.asin!r}"
    if not p.name or not p.name.strip():
        return False, "missing_name"
    if not p.affiliate_url:
        return False, "missing_affiliate_url"
    resolved = resolve_image_url(p.asin, p.image_url)
    if not resolved:
        return False, f"no_resolvable_image:asin={p.asin}"
    return True, "ok"

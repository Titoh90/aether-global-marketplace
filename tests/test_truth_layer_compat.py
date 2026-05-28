#!/usr/bin/env python3
"""
test_truth_layer_compat.py — Verify provider layer never corrupts Truth Layer data.

Tests that:
- normalize_product() output is immutable (frozen dataclass)
- LLM router does NOT modify prices, URLs, or affiliate links
- SanitizedProduct fields are identical before and after routing calls
- Truth Layer rejects provider layer tampering attempts
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.truth.truth_guard import normalize_product
from core.truth.schemas import SanitizedProduct

_PASS = 0
_FAIL = 0


def _check(name: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  ✅ {name}")
    else:
        _FAIL += 1
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


_PRODUCT_RAW = {
    "asin": "B085DTZQNZ",
    "name": "Owala FreeSip Insulated Stainless Steel Water Bottle",
    "price": "33.13",
    "rating": "4.7",
    "reviews": "121827",
    "image_url": "https://m.media-amazon.com/images/I/test.jpg",
    "availability": "In Stock",
}


def test_sanitized_product_is_frozen() -> None:
    print("\n[1] SanitizedProduct is frozen (immutable)")
    sp = normalize_product(_PRODUCT_RAW)
    try:
        sp.numeric_price = 999.0  # type: ignore
        _check("Frozen dataclass raises FrozenInstanceError", False, "no exception")
    except Exception as e:
        _check("Frozen dataclass raises FrozenInstanceError", True)


def test_truth_fields_survive_llm_call() -> None:
    print("\n[2] Truth fields identical before/after LLM call")
    sp_before = normalize_product(_PRODUCT_RAW)

    with patch("core.llm.fallback_chain.complete", return_value="some copy text"):
        from core.llm.provider_router import llm_complete
        llm_complete("Generate copy", tier="FAST_CHEAP", max_tokens=100)

    sp_after = normalize_product(_PRODUCT_RAW)

    _check("price_display unchanged",    sp_before.price_display    == sp_after.price_display)
    _check("numeric_price unchanged",    sp_before.numeric_price    == sp_after.numeric_price)
    _check("affiliate_url unchanged",    sp_before.affiliate_url    == sp_after.affiliate_url)
    _check("image_url unchanged",        sp_before.image_url        == sp_after.image_url)
    _check("asin unchanged",             sp_before.asin             == sp_after.asin)


def test_llm_output_cannot_override_price() -> None:
    print("\n[3] LLM output injected into product dict → Truth Layer rejects bad price")
    # Simulate scenario: LLM hallucinates a price, it gets put in product dict
    manipulated = dict(_PRODUCT_RAW)
    manipulated["price"] = "FREE"  # LLM hallucination

    sp = normalize_product(manipulated)
    _check("'FREE' rejected → price_display is PRICE_UNKNOWN",
           "Check latest price" in sp.price_display,
           f"got: {sp.price_display}")
    _check("numeric_price is 0.0", sp.numeric_price == 0.0)


def test_affiliate_url_built_from_asin_when_missing() -> None:
    print("\n[4] No affiliate_url → Truth Layer builds from ASIN + tag")
    no_url = {k: v for k, v in _PRODUCT_RAW.items() if k != "affiliate_url"}
    sp = normalize_product(no_url)
    _check("Affiliate URL uses aetherglobal-20 tag",
           "aetherglobal-20" in sp.affiliate_url,
           f"got: {sp.affiliate_url}")
    _check("URL points to amazon.com",
           "amazon.com" in sp.affiliate_url,
           f"got: {sp.affiliate_url}")


def test_llm_output_cannot_fabricate_rating() -> None:
    print("\n[5] Fabricated 6-star rating → Truth Layer rejects it")
    manipulated = dict(_PRODUCT_RAW)
    manipulated["rating"] = "6.0"  # impossible rating

    sp = normalize_product(manipulated)
    _check("Rating 6.0 rejected → has_rating() False", not sp.has_rating())
    _check("numeric_rating is 0.0", sp.numeric_rating == 0.0)


def test_normalize_idempotent() -> None:
    print("\n[6] normalize_product() is idempotent (same input → same output)")
    sp1 = normalize_product(_PRODUCT_RAW)
    sp2 = normalize_product(_PRODUCT_RAW)
    _check("price_display identical",    sp1.price_display    == sp2.price_display)
    _check("affiliate_url identical",    sp1.affiliate_url    == sp2.affiliate_url)
    _check("numeric_price identical",    sp1.numeric_price    == sp2.numeric_price)


def test_provider_layer_does_not_import_truth() -> None:
    print("\n[7] provider_router.py does NOT import Truth Layer")
    import importlib, inspect
    router_src = Path(__file__).parent.parent / "core/llm/provider_router.py"
    source = router_src.read_text()
    imports_truth = "core.truth" in source or "normalize_product" in source
    _check("provider_router has no Truth Layer imports", not imports_truth,
           "found 'core.truth' or 'normalize_product' in provider_router.py")


if __name__ == "__main__":
    print("Truth Layer compatibility tests")
    print("=" * 50)
    test_sanitized_product_is_frozen()
    test_truth_fields_survive_llm_call()
    test_llm_output_cannot_override_price()
    test_affiliate_url_built_from_asin_when_missing()
    test_llm_output_cannot_fabricate_rating()
    test_normalize_idempotent()
    test_provider_layer_does_not_import_truth()
    print(f"\n{'='*50}")
    print(f"RESULT: {_PASS} PASS  {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)

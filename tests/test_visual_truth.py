#!/usr/bin/env python3
"""
test_visual_truth.py — Tests for the Visual Truth subsystem.

Tests:
  - ColorPalette schema (frozen, round-trip, fallback)
  - product_color_extractor (name→hex mapping, fallback, palette similarity math)
  - carousel_validator (similarity scoring, threshold logic, ValidationResult)
  - bio_updater (idempotency logic, URL validation gate)

No network calls. No file I/O to production dirs.
"""

from __future__ import annotations

import sys
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

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


# ── ColorPalette schema ───────────────────────────────────────────────────────

def test_color_palette_schema() -> None:
    print("\n[1] ColorPalette schema")
    from core.visual_truth.schemas import ColorPalette

    p = ColorPalette(
        product_id="B085DTZQNZ",
        hex_colors=("#1A1A1A", "#FFFFFF", "#E8D5B0"),
        primary_hex="#1A1A1A",
        source="image_kmeans",
        extracted_at="2026-05-26T10:00:00Z",
    )
    _check("frozen dataclass",     isinstance(p, ColorPalette))
    _check("to_dict() works",      isinstance(p.to_dict(), dict))
    _check("hex_colors in dict",   isinstance(p.to_dict()["hex_colors"], list))
    _check("round-trip",           ColorPalette.from_dict(p.to_dict()) == p)

    try:
        p.primary_hex = "mutate"  # type: ignore
        _check("immutable", False)
    except Exception:
        _check("immutable", True)

    # Fallback
    fb = ColorPalette.fallback("B085DTZQNZ")
    _check("fallback source='fallback'", fb.source == "fallback")
    _check("fallback has colors",        len(fb.hex_colors) > 0)


# ── ValidationResult schema ───────────────────────────────────────────────────

def test_validation_result_schema() -> None:
    print("\n[2] ValidationResult schema")
    from core.visual_truth.schemas import SlideValidation, ValidationResult

    sv = SlideValidation(
        slide_index=0,
        slide_path="/tmp/slide_0.png",
        similarity_score=0.82,
        passed=True,
        dominant_hex=("#1A1A1A", "#FFFFFF"),
    )
    _check("SlideValidation to_dict", isinstance(sv.to_dict(), dict))
    _check("score rounded",           sv.to_dict()["similarity_score"] == 0.82)

    vr = ValidationResult(
        passed=True,
        product_id="B085DTZQNZ",
        slide_results=(sv,),
        threshold=0.65,
        failed_count=0,
        action="publish",
        validated_at="2026-05-26T10:00:00Z",
    )
    d = vr.to_dict()
    _check("ValidationResult to_dict",        isinstance(d, dict))
    _check("slide_results is list in dict",   isinstance(d["slide_results"], list))
    _check("action=publish on full pass",     d["action"] == "publish")


# ── color name → hex mapping ──────────────────────────────────────────────────

def test_color_name_mapping() -> None:
    print("\n[3] product_color_extractor — name→hex mapping")
    from core.visual_truth.product_color_extractor import _name_to_hex, palette_from_metadata

    _check("'black' → hex",          _name_to_hex("black") == "#1A1A1A")
    _check("'White' (caps) → hex",   _name_to_hex("White") is not None)
    _check("'teal' → hex",           _name_to_hex("teal") == "#007B7B")
    _check("'unknown123' → None",    _name_to_hex("unknown123") is None)
    _check("'Dark Navy Blue' partial", _name_to_hex("Dark Navy Blue") is not None)

    # palette_from_metadata
    pal = palette_from_metadata("B085DTZQNZ", ["Black", "Teal", "Unknown"])
    _check("metadata palette built",     pal.source == "amazon_metadata")
    _check("unknown color filtered",     len(pal.hex_colors) == 2)
    _check("primary_hex = first color",  pal.primary_hex == pal.hex_colors[0])

    # all unknown → fallback
    pal_fb = palette_from_metadata("B085DTZQNZ", ["XYZ123", "???"])
    _check("all-unknown → fallback",     pal_fb.source == "fallback")


# ── HSV distance math ─────────────────────────────────────────────────────────

def test_hsv_distance_math() -> None:
    print("\n[4] carousel_validator — HSV distance math")
    from core.visual_truth.carousel_validator import _hex_to_hsv, _hsv_distance, palette_similarity

    black_hsv = _hex_to_hsv("#000000")
    white_hsv = _hex_to_hsv("#FFFFFF")
    _check("black HSV V=0",  black_hsv[2] == 0.0)
    _check("white HSV V=1",  white_hsv[2] == 1.0)
    _check("black S=0",      black_hsv[1] == 0.0)

    # Distance: same color = 0
    same_dist = _hsv_distance(black_hsv, black_hsv)
    _check("same color distance = 0", same_dist == 0.0)

    # Distance: black vs white > 0
    bw_dist = _hsv_distance(black_hsv, white_hsv)
    _check("black vs white distance > 0", bw_dist > 0)

    # Hue wrap-around: #FF0000 (H=0) vs #FF00FF (H≈0.833) should be similar hue distance
    # to #FF0000 (H=0) vs #00FF00 (H=0.333)
    red_hsv     = _hex_to_hsv("#FF0000")
    magenta_hsv = _hex_to_hsv("#FF00FF")
    green_hsv   = _hex_to_hsv("#00FF00")
    d_red_mag = _hsv_distance(red_hsv, magenta_hsv)
    d_red_grn = _hsv_distance(red_hsv, green_hsv)
    _check("hue wrap: red↔magenta < red↔green", d_red_mag < d_red_grn)

    # palette_similarity: identical palettes → 1.0
    same_sim = palette_similarity(["#1A1A1A", "#FFFFFF"], ["#1A1A1A", "#FFFFFF"])
    _check("identical palettes → similarity ≈ 1.0", abs(same_sim - 1.0) < 0.01)

    # palette_similarity: completely different → low score
    diff_sim = palette_similarity(["#000000"], ["#FFFFFF"])
    _check("black vs white similarity < 0.5", diff_sim < 0.5)

    # edge cases
    _check("empty A → 0.0", palette_similarity([], ["#000000"]) == 0.0)
    _check("empty B → 0.0", palette_similarity(["#000000"], []) == 0.0)

    # similar shades → high similarity
    near_sim = palette_similarity(["#1A1A1A", "#1C1C1C"], ["#1A1A1A", "#202020"])
    _check("near-black shades → high similarity", near_sim > 0.9)


# ── ValidationResult gate logic ───────────────────────────────────────────────

def test_validation_gate_logic() -> None:
    print("\n[5] carousel_validator — gate logic (no real images)")
    from core.visual_truth.carousel_validator import validate_carousel_palette, DEFAULT_THRESHOLD
    from core.visual_truth.schemas import ColorPalette

    ref = ColorPalette(
        product_id="B085DTZQNZ",
        hex_colors=("#1A1A1A", "#FFFFFF"),
        primary_hex="#1A1A1A",
        source="image_kmeans",
        extracted_at="2026-05-26T10:00:00Z",
    )

    # Non-existent paths → SlideValidation.passed=False for each
    fake_paths = [Path("/tmp/nonexistent_slide_0.png"), Path("/tmp/nonexistent_slide_1.png")]
    result = validate_carousel_palette(fake_paths, ref, threshold=DEFAULT_THRESHOLD)

    _check("returns ValidationResult",       hasattr(result, "passed"))
    _check("failed_count = 2",               result.failed_count == 2)
    _check("action = log_warning",           result.action == "log_warning")
    _check("passed = False",                 result.passed is False)
    _check("slide_results has 2 entries",    len(result.slide_results) == 2)
    _check("each slide has similarity_score", all(hasattr(sv, "similarity_score") for sv in result.slide_results))


# ── bio_updater URL validation gate ──────────────────────────────────────────

def test_bio_updater_url_gate() -> None:
    print("\n[6] bio_updater — URL validation gate")
    from core.visual_truth.bio_updater import update_bio_link

    # URL without affiliate tag → should fail at validation, not attempt network call
    bad_url = "https://www.amazon.com/dp/B085DTZQNZ?utm_source=instagram&utm_medium=social"
    result = update_bio_link(bad_url, "instagram")
    _check("bad URL → action=failed",   result.action == "failed")
    _check("bad URL → success=False",   result.success is False)
    _check("error message populated",   len(result.error) > 0)
    _check("no network call attempted", "URL validation failed" in result.error)

    # Unsupported platform
    from revenue_layer.affiliate_link_builder import build
    good_url = build("B085DTZQNZ", "post_001", "instagram")
    result2 = update_bio_link(good_url, "snapchat")
    _check("unsupported platform → failed", result2.action == "failed")
    _check("error mentions platform",       "snapchat" in result2.error.lower() or "Unsupported" in result2.error)


# ── Fallback chain in extractor ───────────────────────────────────────────────

def test_extractor_fallback_chain() -> None:
    print("\n[7] product_color_extractor — fallback chain")
    from core.visual_truth.product_color_extractor import get_dominant_palette

    # Empty URL → fallback immediately
    result = get_dominant_palette("", "B085DTZQNZ")
    _check("empty URL → source=fallback",   result.source == "fallback")
    _check("fallback has hex_colors",       len(result.hex_colors) > 0)
    _check("fallback never raises",         True)

    # Unreachable URL → fallback (timeout)
    result2 = get_dominant_palette("http://localhost:19999/nonexistent.jpg", "B085DTZQNZ")
    _check("unreachable URL → fallback",    result2.source == "fallback")
    _check("product_id preserved",          result2.product_id == "B085DTZQNZ")


if __name__ == "__main__":
    print("Visual Truth subsystem tests")
    print("=" * 50)

    test_color_palette_schema()
    test_validation_result_schema()
    test_color_name_mapping()
    test_hsv_distance_math()
    test_validation_gate_logic()
    test_bio_updater_url_gate()
    test_extractor_fallback_chain()

    print(f"\n{'='*50}")
    print(f"RESULT: {_PASS} PASS  {_FAIL} FAIL")
    import sys
    sys.exit(0 if _FAIL == 0 else 1)

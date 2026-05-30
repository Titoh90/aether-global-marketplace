#!/usr/bin/env python3
"""
carousel_validator.py — Post-generation palette validation gate.

Validates that generated carousel slides are visually coherent
with the reference product color palette BEFORE publishing.

Algorithm:
  For each slide:
    1. Extract dominant palette from generated image (same k-means as extractor)
    2. Compute palette_similarity(generated, reference)
       - For each generated color: find closest reference color in HSV space
       - Score = mean(1 - normalized_min_distance) across all generated colors
    3. Slide passes if similarity >= threshold

Scoring:
  - 1.0 = identical palette
  - 0.8+ = very consistent
  - 0.65 = default threshold (allows creative freedom in background/lighting)
  - 0.0 = completely different palette

Policy (v1):
  - Failures → ValidationResult.action = "log_warning" (publish with warning)
  - NOT "reject" in v1 — Flow output is hard to control deterministically
  - Future: "reject" + requeue when we have retry budget

Output:
  - ValidationResult written to logs/visual_truth/YYYY-MM-DD.jsonl
  - Always emitted — even full-pass runs are logged (audit trail)

ZERO AI calls. ZERO mutation of generated files. Read-only analysis.
"""

from __future__ import annotations

import colorsys
import datetime
import json
import math
import sys
import threading
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.visual_truth.schemas import ColorPalette, SlideValidation, ValidationResult
from core.visual_truth.product_color_extractor import _extract_hex_palette

_LOG_DIR = _IMPERIO_ROOT / "logs" / "visual_truth"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()

# ── Configuration ─────────────────────────────────────────────────────────────

DEFAULT_THRESHOLD = 0.65   # similarity floor — below this → warning
_N_SLIDE_COLORS   = 5      # colors to extract per slide
_MAX_HSV_DIST     = math.sqrt(1**2 + 1**2 + 1**2)  # max possible HSV euclidean dist


# ── Public API ────────────────────────────────────────────────────────────────

def validate_carousel_palette(
    generated_paths: list[Path],
    reference:       ColorPalette,
    threshold:       float = DEFAULT_THRESHOLD,
    product_id:      str   = "",
) -> ValidationResult:
    """
    Validate generated carousel slides against reference color palette.

    Args:
        generated_paths: list of paths to generated PNG slides
        reference:       ColorPalette from product_color_extractor (truth anchor)
        threshold:       minimum similarity score to pass (default 0.65)
        product_id:      for logging; falls back to reference.product_id

    Returns:
        ValidationResult — always returns (never raises)
        Writes result to logs/visual_truth/YYYY-MM-DD.jsonl

    Side effects:
        Logs to visual_truth JSONL. Nothing else.
    """
    pid      = product_id or reference.product_id
    ts       = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ref_hexes = list(reference.hex_colors)

    slide_results: list[SlideValidation] = []

    for i, path in enumerate(generated_paths):
        sv = _validate_slide(i, path, ref_hexes, threshold)
        slide_results.append(sv)

    failed = sum(1 for sv in slide_results if not sv.passed)
    passed = failed == 0

    # v1 policy: never "reject" — always "publish" or "log_warning"
    action = "publish" if passed else "log_warning"

    result = ValidationResult(
        passed=passed,
        product_id=pid,
        slide_results=tuple(slide_results),
        threshold=threshold,
        failed_count=failed,
        action=action,
        validated_at=ts,
    )

    _log(result)
    return result


def palette_similarity(hex_a: list[str], hex_b: list[str]) -> float:
    """
    Compute similarity between two color palettes. Public for testing.

    Algorithm: for each color in A, find its closest match in B (min HSV distance).
    Score = mean of (1 - normalized_distance) across all A colors.
    Range: 0.0 (no overlap) to 1.0 (identical).

    Symmetric: similarity(A, B) ≈ similarity(B, A) (not exact due to mean direction)
    """
    if not hex_a or not hex_b:
        return 0.0

    hsv_a = [_hex_to_hsv(h) for h in hex_a if h]
    hsv_b = [_hex_to_hsv(h) for h in hex_b if h]

    if not hsv_a or not hsv_b:
        return 0.0

    scores = []
    for ca in hsv_a:
        min_dist = min(_hsv_distance(ca, cb) for cb in hsv_b)
        normalized = min_dist / _MAX_HSV_DIST
        scores.append(1.0 - normalized)

    return sum(scores) / len(scores)


# ── Internals ─────────────────────────────────────────────────────────────────

def _validate_slide(
    index:     int,
    path:      Path,
    ref_hexes: list[str],
    threshold: float,
) -> SlideValidation:
    """Extract slide palette and compute similarity. Never raises."""
    try:
        if not path.exists():
            return SlideValidation(
                slide_index=index,
                slide_path=str(path),
                similarity_score=0.0,
                passed=False,
                dominant_hex=(),
            )

        img_bytes = path.read_bytes()
        slide_hexes = _extract_hex_palette(img_bytes, _N_SLIDE_COLORS)

        if not slide_hexes:
            # Can't extract palette — treat as unknown, pass with 0 score logged
            return SlideValidation(
                slide_index=index,
                slide_path=str(path),
                similarity_score=0.0,
                passed=False,
                dominant_hex=(),
            )

        score = palette_similarity(slide_hexes, ref_hexes)
        return SlideValidation(
            slide_index=index,
            slide_path=str(path),
            similarity_score=score,
            passed=score >= threshold,
            dominant_hex=tuple(slide_hexes),
        )

    except Exception:
        return SlideValidation(
            slide_index=index,
            slide_path=str(path),
            similarity_score=0.0,
            passed=False,
            dominant_hex=(),
        )


def _hex_to_hsv(hex_color: str) -> tuple:
    """Convert hex color string to (H, S, V) tuple. H in [0,1], S in [0,1], V in [0,1]."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (0.0, 0.0, 0.5)
    try:
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return colorsys.rgb_to_hsv(r, g, b)
    except ValueError:
        return (0.0, 0.0, 0.5)


def _hsv_distance(a: tuple, b: tuple) -> float:
    """
    Euclidean distance in HSV space.
    Hue is circular — use min(|dH|, 1-|dH|) to handle wrap-around.
    """
    dh = min(abs(a[0] - b[0]), 1.0 - abs(a[0] - b[0]))
    ds = abs(a[1] - b[1])
    dv = abs(a[2] - b[2])
    return math.sqrt(dh**2 + ds**2 + dv**2)


def _log(result: ValidationResult) -> None:
    """Append validation result to daily JSONL log."""
    date_str = datetime.date.today().isoformat()
    log_file = _LOG_DIR / f"{date_str}.jsonl"
    line     = json.dumps(result.to_dict(), ensure_ascii=False)
    with _lock:
        with open(log_file, "a") as f:
            f.write(line + "\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Validate carousel slides against a reference palette"
    )
    parser.add_argument("--slides",    nargs="+", required=True, help="Paths to generated slides")
    parser.add_argument("--ref-hex",   nargs="+", required=True, help="Reference hex colors e.g. #1A1A1A")
    parser.add_argument("--product",   default="CLI_TEST")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = parser.parse_args()

    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ref = ColorPalette(
        product_id=args.product,
        hex_colors=tuple(args.ref_hex),
        primary_hex=args.ref_hex[0],
        source="cli_input",
        extracted_at=ts,
    )
    paths = [Path(p) for p in args.slides]
    result = validate_carousel_palette(paths, ref, threshold=args.threshold, product_id=args.product)

    print(json.dumps(result.to_dict(), indent=2))
    if result.action == "log_warning":
        print(f"\n⚠️  {result.failed_count} slide(s) below threshold {args.threshold}")
    else:
        print(f"\n✅ All {len(args.slides)} slides pass")

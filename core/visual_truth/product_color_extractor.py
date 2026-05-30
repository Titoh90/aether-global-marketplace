#!/usr/bin/env python3
"""
product_color_extractor.py — Extract ground-truth color palette from product images.

Strategy:
  1. Download Amazon product image (URL from get_amazon_product_image())
  2. Resize to 150×150 for fast processing
  3. Quantize to N dominant colors via PIL adaptive palette
  4. Return ColorPalette with hex codes ordered by pixel count (most dominant first)

Why image-based, not metadata:
  - Metadata: "Black" → no luminance, no saturation, no actual hex
  - Image k-means: "#1A1A1A" vs "#000000" vs "#2C2C2C" — real visual data
  - Enables HSV-space similarity comparison in carousel_validator

Fallback chain:
  image_kmeans → amazon_metadata (text parse) → fallback neutral palette
  NEVER blocks pipeline — always returns a ColorPalette

ZERO AI calls. ZERO writes to disk. Pure in-memory extraction.
"""

from __future__ import annotations

import colorsys
import datetime
import sys
import urllib.request
from io import BytesIO
from pathlib import Path
from typing import Optional

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.visual_truth.schemas import ColorPalette

# ── Constants ─────────────────────────────────────────────────────────────────

_RESIZE_DIM        = 150          # px — resize before extraction (speed)
_DEFAULT_N_COLORS  = 5            # dominant colors to extract
_DOWNLOAD_TIMEOUT  = 8            # seconds

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/webp,image/png,image/*,*/*",
}


# ── Public API ────────────────────────────────────────────────────────────────

def get_dominant_palette(
    image_url:  str,
    product_id: str,
    n:          int = _DEFAULT_N_COLORS,
) -> ColorPalette:
    """
    Extract dominant color palette from a product image URL.

    Args:
        image_url:  URL of the Amazon product image
        product_id: ASIN or internal ID (for traceability)
        n:          number of dominant colors to extract (default 5)

    Returns:
        ColorPalette with source="image_kmeans" on success,
        source="fallback" if image cannot be downloaded/processed.

    Never raises — all errors produce a fallback ColorPalette.
    """
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if not image_url or not image_url.strip():
        return ColorPalette.fallback(product_id)

    try:
        img_bytes = _download_image(image_url)
        hex_colors = _extract_hex_palette(img_bytes, n)
        if not hex_colors:
            return ColorPalette.fallback(product_id)

        return ColorPalette(
            product_id=product_id,
            hex_colors=tuple(hex_colors),
            primary_hex=hex_colors[0],
            source="image_kmeans",
            extracted_at=ts,
        )

    except Exception:
        return ColorPalette.fallback(product_id)


def palette_from_metadata(
    product_id:    str,
    color_strings: list[str],    # e.g. ["Black", "Teal", "Cream"]
) -> ColorPalette:
    """
    Build ColorPalette from Amazon metadata color names.
    Fallback when image is unavailable.
    Used by carousel_flow.get_amazon_product_colors() as secondary source.
    """
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    hex_colors = [_name_to_hex(c) for c in color_strings if c]
    hex_colors = [h for h in hex_colors if h]  # filter None

    if not hex_colors:
        return ColorPalette.fallback(product_id)

    return ColorPalette(
        product_id=product_id,
        hex_colors=tuple(hex_colors),
        primary_hex=hex_colors[0],
        source="amazon_metadata",
        extracted_at=ts,
    )


# ── Internal ──────────────────────────────────────────────────────────────────

def _download_image(url: str) -> bytes:
    """Download image bytes. Raises on network failure."""
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_DOWNLOAD_TIMEOUT) as resp:
        return resp.read()


def _extract_hex_palette(img_bytes: bytes, n: int) -> list[str]:
    """
    Extract N dominant colors from image bytes using PIL quantization.

    PIL's adaptive palette quantization is fast (no scipy/sklearn needed)
    and produces perceptually good dominant colors.

    Returns list of hex strings ordered by pixel count (most dominant first).
    """
    try:
        from PIL import Image
    except ImportError:
        return []

    img = Image.open(BytesIO(img_bytes)).convert("RGB")

    # Resize for speed — 150×150 preserves color distribution
    img = img.resize((_RESIZE_DIM, _RESIZE_DIM), Image.LANCZOS)

    # Quantize to N colors using PIL's adaptive palette
    quantized = img.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    palette_data = quantized.getpalette()  # flat list: [R,G,B, R,G,B, ...]

    if not palette_data:
        return []

    # Count pixels per color index to sort by dominance
    pixel_counts: dict[int, int] = {}
    for px in quantized.getdata():
        pixel_counts[px] = pixel_counts.get(px, 0) + 1

    # Sort color indices by pixel count descending
    sorted_indices = sorted(pixel_counts.keys(), key=lambda i: pixel_counts[i], reverse=True)

    hex_colors = []
    for idx in sorted_indices[:n]:
        if idx * 3 + 2 < len(palette_data):
            r = palette_data[idx * 3]
            g = palette_data[idx * 3 + 1]
            b = palette_data[idx * 3 + 2]
            hex_colors.append(_rgb_to_hex(r, g, b))

    return hex_colors


def _rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


# ── Color name → hex lookup ───────────────────────────────────────────────────
# Amazon metadata often uses these color names. Map to representative hex.
# Not exhaustive — unrecognized names return None and are filtered out.

_COLOR_NAME_MAP: dict[str, str] = {
    "black":         "#1A1A1A",
    "white":         "#F5F5F5",
    "red":           "#CC2200",
    "blue":          "#1A4A8A",
    "navy":          "#1B2A4A",
    "green":         "#2E7D32",
    "olive":         "#6B6B00",
    "teal":          "#007B7B",
    "cyan":          "#00BCD4",
    "purple":        "#6A1B9A",
    "lavender":      "#9575CD",
    "pink":          "#E91E8C",
    "rose":          "#E07070",
    "orange":        "#E65100",
    "amber":         "#FF8F00",
    "yellow":        "#F9A825",
    "gold":          "#B8860B",
    "cream":         "#FFF8E1",
    "ivory":         "#FFFFF0",
    "beige":         "#F5F0E0",
    "tan":           "#D2B48C",
    "brown":         "#5D4037",
    "chocolate":     "#3E2723",
    "gray":          "#757575",
    "grey":          "#757575",
    "silver":        "#B0B0B0",
    "charcoal":      "#424242",
    "slate":         "#607D8B",
    "coral":         "#FF6B6B",
    "mint":          "#A5D6A7",
    "sage":          "#8FAF8A",
    "turquoise":     "#26C6DA",
    "indigo":        "#3F51B5",
    "violet":        "#7B1FA2",
    "magenta":       "#AD1457",
    "fuchsia":       "#E91E63",
    "lime":          "#AFB42B",
    "maroon":        "#880E4F",
    "burgundy":      "#7B1C2A",
    "wine":          "#722F37",
    "rose gold":     "#B76E79",
    "copper":        "#B87333",
    "bronze":        "#8C6C3E",
    "champagne":     "#F7E7CE",
    "pearl":         "#F0EDE8",
    "clear":         "#FAFAFA",
    "transparent":   "#FAFAFA",
    "multicolor":    "#808080",
    "multi":         "#808080",
}


def _name_to_hex(name: str) -> Optional[str]:
    """Map color name string → hex. Case-insensitive. Returns None if unrecognized."""
    cleaned = name.strip().lower()
    # Direct match
    if cleaned in _COLOR_NAME_MAP:
        return _COLOR_NAME_MAP[cleaned]
    # Partial match (e.g. "Dark Navy Blue" → try each word)
    for word in cleaned.split():
        if word in _COLOR_NAME_MAP:
            return _COLOR_NAME_MAP[word]
    return None


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse, json
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",     required=True, help="Image URL to analyze")
    parser.add_argument("--product", default="TEST", help="Product ID")
    parser.add_argument("--n",       type=int, default=5, help="Number of colors")
    args = parser.parse_args()

    palette = get_dominant_palette(args.url, args.product, args.n)
    print(json.dumps(palette.to_dict(), indent=2))

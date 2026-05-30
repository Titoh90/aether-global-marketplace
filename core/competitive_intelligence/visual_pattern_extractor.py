#!/usr/bin/env python3
"""
visual_pattern_extractor.py — Detects visual styles from public post metadata.

Uses dispatch("visual_analysis") for AI-powered classification.
Local heuristic fallback for common visual patterns.

NEVER stores images, pixel data, or raw media.
ONLY extracts style labels and composition classifications.

Usage:
    from core.competitive_intelligence.visual_pattern_extractor import classify_visual_style
"""

from __future__ import annotations

import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.competitive_intelligence.schemas import VISUAL_STYLES

# ── Local heuristic patterns (fallback when dispatch unavailable) ─────────────

_STYLE_KEYWORDS: dict[str, list[str]] = {
    "luxury_dark":          ["dark", "black", "gold", "luxury", "premium", "velvet", "shadow", "oscuro", "negro", "dorado", "lujo"],
    "minimal_clean":        ["white", "clean", "minimal", "simple", "blanco", "limpio", "minimalista", "sencillo", "plain"],
    "warm_lifestyle":       ["warm", "cozy", "home", "lifestyle", "natural", "sunlight", "cálido", "hogar", "natural", "luz"],
    "cinematic_commercial": ["cinematic", "dramatic", "film", "commercial", "studio", "cinemático", "dramático", "estudio"],
    "tech_premium":         ["tech", "blue", "neon", "digital", "futuristic", "led", "tecnología", "azul", "neón", "digital"],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _local_classify(description: str) -> tuple[str, float]:
    """Local heuristic visual style classification."""
    text = description.lower()
    scores: dict[str, float] = {}

    for style, keywords in _STYLE_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw.lower() in text)
        if matches > 0:
            scores[style] = min(matches / len(keywords), 1.0)

    if not scores:
        return ("unknown", 0.0)

    best = max(scores, key=lambda k: scores[k])
    return (best, scores[best])


def _dispatch_classify(description: str) -> tuple[str, float]:
    """AI-powered visual style classification via dispatch layer."""
    from core.inference_dispatch.dispatch import dispatch

    prompt = (
        f"Classify this visual description into EXACTLY ONE of: {', '.join(sorted(VISUAL_STYLES))}.\n\n"
        f"Description: {description}\n\n"
        f"Respond with ONLY the style label (one phrase). Nothing else."
    )

    result = dispatch(
        task_type="visual_analysis",
        payload={"prompt": prompt},
        max_tokens=16,
    )

    if result.success:
        raw = result.text.strip().lower().replace(" ", "_").replace("-", "_")
        for style in VISUAL_STYLES:
            if style in raw:
                return (style, 0.85)

    # Fall back to local
    return _local_classify(description)


# ── Public API ────────────────────────────────────────────────────────────────

def classify_visual_style(
    description:         str,
    color_palette_hint:  str = "",
    composition_hint:    str = "",
) -> tuple[str, float, str, str]:
    """
    Classify visual style from a description.

    Args:
        description:         text description of visual appearance
        color_palette_hint:  known color palette info
        composition_hint:    known composition info

    Returns:
        (style_label, confidence, color_palette, composition) — never raises.
    """
    full_text = description
    if color_palette_hint:
        full_text += f" colors: {color_palette_hint}"
    if composition_hint:
        full_text += f" composition: {composition_hint}"

    try:
        style, confidence = _dispatch_classify(full_text)
    except Exception:
        style, confidence = _local_classify(full_text)

    # Extract color palette if not provided
    palette = color_palette_hint if color_palette_hint else _infer_palette(description)

    # Extract composition if not provided
    comp = composition_hint if composition_hint else _infer_composition(description)

    return (style, confidence, palette, comp)


def _infer_palette(description: str) -> str:
    """Infer dominant color palette from description."""
    text = description.lower()
    if any(w in text for w in ["dark", "black", "oscuro", "negro"]):
        return "dark_monochrome"
    if any(w in text for w in ["white", "bright", "blanco", "brillante"]):
        return "light_clean"
    if any(w in text for w in ["warm", "gold", "cálido", "dorado"]):
        return "warm_tones"
    if any(w in text for w in ["blue", "cool", "azul", "frío"]):
        return "cool_tones"
    if any(w in text for w in ["neon", "vibrant", "neón", "vibrante"]):
        return "vibrant_pop"
    return "unknown"


def _infer_composition(description: str) -> str:
    """Infer composition/framing from description."""
    text = description.lower()
    if any(w in text for w in ["centered", "center", "centro", "centrado"]):
        return "center_product"
    if any(w in text for w in ["lifestyle", "scene", "escena"]):
        return "lifestyle_wide"
    if any(w in text for w in ["close", "detail", "macro", "cerca", "detalle"]):
        return "close_up_detail"
    if any(w in text for w in ["flat", "layout", "plano"]):
        return "flat_lay"
    if any(w in text for w in ["text", "overlay", "texto"]):
        return "text_overlay_heavy"
    return "unknown"


def classify_batch(
    descriptions: list[dict],
) -> list[tuple[str, float, str, str]]:
    """Classify a batch of visual descriptions."""
    return [
        classify_visual_style(
            description=d.get("description", ""),
            color_palette_hint=d.get("color_palette", ""),
            composition_hint=d.get("composition", ""),
        )
        for d in descriptions
    ]

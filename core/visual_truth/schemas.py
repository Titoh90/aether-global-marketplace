#!/usr/bin/env python3
"""
schemas.py — Canonical types for the Visual Truth subsystem.

Frozen dataclasses — immutable once created, serializable to dict/JSON.

ColorPalette:    ground-truth color vector extracted from real product image
SlideValidation: per-slide result from carousel_validator
ValidationResult: aggregate gate result for a full carousel run
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class ColorPalette:
    """
    Ground-truth color palette for a product.

    source hierarchy (most trustworthy first):
      "image_kmeans"      — extracted directly from Amazon product image via k-means
      "amazon_metadata"   — parsed from Amazon listing text/JSON (color name strings)
      "fallback"          — default neutral palette when extraction fails

    hex_colors: ordered by dominance (most dominant first)
    primary_hex: single most dominant color
    """
    product_id:   str
    hex_colors:   tuple          # tuple[str, ...] — ordered by dominance
    primary_hex:  str            # most dominant
    source:       str            # "image_kmeans" | "amazon_metadata" | "fallback"
    extracted_at: str            # ISO 8601 UTC

    def to_dict(self) -> dict:
        return {
            "product_id":   self.product_id,
            "hex_colors":   list(self.hex_colors),
            "primary_hex":  self.primary_hex,
            "source":       self.source,
            "extracted_at": self.extracted_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ColorPalette":
        return cls(
            product_id=d["product_id"],
            hex_colors=tuple(d["hex_colors"]),
            primary_hex=d["primary_hex"],
            source=d.get("source", "unknown"),
            extracted_at=d.get("extracted_at", ""),
        )

    @classmethod
    def fallback(cls, product_id: str) -> "ColorPalette":
        """Neutral fallback palette when extraction fails. Never blocks pipeline."""
        ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return cls(
            product_id=product_id,
            hex_colors=("#FFFFFF", "#000000", "#808080"),
            primary_hex="#808080",
            source="fallback",
            extracted_at=ts,
        )


@dataclass(frozen=True)
class SlideValidation:
    """Per-slide result from carousel_validator."""
    slide_index:      int
    slide_path:       str     # absolute path to generated image
    similarity_score: float   # 0.0–1.0 (1.0 = identical palette)
    passed:           bool    # True if similarity_score >= threshold
    dominant_hex:     tuple   # tuple[str, ...] — palette extracted from generated slide

    def to_dict(self) -> dict:
        return {
            "slide_index":      self.slide_index,
            "slide_path":       self.slide_path,
            "similarity_score": round(self.similarity_score, 4),
            "passed":           self.passed,
            "dominant_hex":     list(self.dominant_hex),
        }


@dataclass(frozen=True)
class ValidationResult:
    """
    Aggregate gate result for one carousel run.

    passed:       True if ALL slides pass threshold (strict gate)
    failed_count: number of slides below threshold
    action:       "publish" | "log_warning" | "reject"

    Policy (set by caller):
      - passed=True  → publish
      - passed=False, action="log_warning" → publish with warning logged
      - passed=False, action="reject"      → do not publish, requeue

    v1 default: log_warning (non-blocking — never silently drop)
    """
    passed:            bool
    product_id:        str
    slide_results:     tuple          # tuple[SlideValidation, ...]
    threshold:         float
    failed_count:      int
    action:            str            # "publish" | "log_warning" | "reject"
    validated_at:      str            # ISO 8601 UTC

    def to_dict(self) -> dict:
        return {
            "passed":        self.passed,
            "product_id":    self.product_id,
            "slide_results": [s.to_dict() for s in self.slide_results],
            "threshold":     self.threshold,
            "failed_count":  self.failed_count,
            "action":        self.action,
            "validated_at":  self.validated_at,
        }

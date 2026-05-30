#!/usr/bin/env python3
"""
schemas.py — Immutable product truth schema.

SanitizedProduct is the ONLY object runtime modules may consume.
Raw Amazon data is NEVER passed to output layers directly.
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SanitizedProduct:
    """
    Immutable, truth-validated product object.
    All fields guaranteed to be safe for direct output — no further guards needed.

    Frozen=True enforces immutability: no module may mutate fields after creation.
    """

    # Identity
    asin: str                          # Always present; empty string if unknown

    # Display fields — safe for direct injection into captions, prompts, slides
    title_clean: str                   # Unicode-clean, normalized whitespace
    price_display: str                 # "$29.99" OR "Check latest price on Amazon"
    rating_display: str                # "4.7/5" OR "" (never fabricated)
    reviews_display: str               # "12,450 reviews" OR "" (never fabricated)
    discount_display: str              # "Save $8.00 (27%)" OR "" (no old_price = no discount)

    # Machine-usable numerics (0.0 / 0 == unknown — never fabricate)
    numeric_price: float               # 0.0 if unknown
    numeric_rating: float              # 0.0 if unknown
    numeric_reviews: int               # 0 if unknown
    numeric_discount_pct: float        # 0.0 if no valid discount

    # URLs
    affiliate_url: str                 # Always present; empty string if unknown
    image_url: str                     # Always present; empty string if unknown

    # Availability
    availability: str                  # "In Stock" | "Check availability" | ""

    # Provenance
    raw_source_timestamp: str          # ISO8601 timestamp from source data, or ""

    # Internal — DO NOT render in user-facing content
    _validation_warnings: tuple = field(default_factory=tuple, compare=False)
    _is_partial: bool = False

    def has_price(self) -> bool:
        return self.numeric_price > 0

    def has_rating(self) -> bool:
        return self.numeric_rating > 0

    def has_reviews(self) -> bool:
        return self.numeric_reviews > 0

    def has_discount(self) -> bool:
        return self.numeric_discount_pct > 0

    def is_complete(self) -> bool:
        """True only when all primary display fields are present."""
        return (
            bool(self.title_clean)
            and self.has_price()
            and self.has_rating()
            and self.has_reviews()
            and bool(self.affiliate_url)
        )

    def to_prompt_context(self) -> str:
        """
        Returns a deterministic prompt context block safe for Claude injection.
        Only includes fields that are verified — never fabricates.
        """
        lines = [f"Product: {self.title_clean}"]
        if self.has_price():
            lines.append(f"Price: {self.price_display}")
        if self.has_rating():
            lines.append(f"Rating: {self.rating_display}")
        if self.has_reviews():
            lines.append(f"Reviews: {self.reviews_display}")
        if self.has_discount():
            lines.append(f"Discount: {self.discount_display}")
        if self.availability:
            lines.append(f"Availability: {self.availability}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"SanitizedProduct(asin={self.asin!r}, title={self.title_clean[:40]!r}, "
            f"price={self.price_display!r}, partial={self._is_partial})"
        )

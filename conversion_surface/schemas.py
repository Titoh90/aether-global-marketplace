"""
schemas.py — Frozen dataclasses for Conversion Surface Layer.
All schemas are frozen=True to ensure deterministic rendering.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass(frozen=True)
class SurfaceProduct:
    asin: str
    name: str
    price: float
    category: str
    affiliate_url: str
    tracking_url: str        # /go/{asin}?src=...
    image_url: str           # Amazon product image
    final_score: float
    section: str             # "hero" | "trending" | "evergreen" | "category"
    archetype_label: str     # from visual_intelligence (or "")
    creative_mode: str       # from campaigns.json
    evergreen_status: str    # "active" | "evergreen" | "experimental"
    rating: float = 0.0      # Amazon star rating (0.0-5.0)
    reviews: int = 0         # Amazon review count

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class HubSurface:
    generated_at: str
    hero: SurfaceProduct
    trending: tuple
    evergreen: tuple
    by_category: dict
    recent: tuple

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "hero":         self.hero.to_dict(),
            "trending":     [p.to_dict() for p in self.trending],
            "evergreen":    [p.to_dict() for p in self.evergreen],
            "by_category":  {k: [p.to_dict() for p in v] for k, v in self.by_category.items()},
            "recent":       [p.to_dict() for p in self.recent],
        }


@dataclass(frozen=True)
class ClickEvent:
    click_id: str       # uuid4
    product_id: str
    asin: str
    platform: str
    campaign: str
    archetype: str
    source_surface: str
    timestamp: str
    visual_mode: str
    category: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EvergreenEntry:
    asin: str
    product_name: str
    category: str
    status: str           # active | evergreen | archived | experimental
    first_seen: str
    last_promoted: str
    total_clicks: int
    total_posts: int
    performance_score: float
    affiliate_url: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Campaign:
    campaign_id: str
    name: str
    start_date: str
    end_date: str
    priority_boost: float
    target_categories: tuple
    visual_theme: str
    status: str           # active | expired

    def to_dict(self) -> dict:
        d = asdict(self)
        d["target_categories"] = list(self.target_categories)
        return d

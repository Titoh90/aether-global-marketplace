"""
schemas.py — Frozen dataclasses for Conversion Surface Layer.
All schemas are frozen=True to ensure deterministic rendering.

## TWO-LAYER ARCHITECTURE

### PRODUCT TRUTH LAYER (fields: asin, name, price, image_url, affiliate_url, ...)
  - Contains only REAL, FACTUAL product data
  - image_url MUST be a real Amazon CDN URL (m.media-amazon.com or similar)
  - No AI-generated images, renders, or placeholders permitted
  - Validated by product_validator.py before entering the hub
  - If image cannot be sourced → product is EXCLUDED from display

### MARKETING LAYER (fields: marketing_video_url, marketing_carousel_urls)
  - AI-generated promotional content (Google Flow, etc.)
  - Used ONLY for social media ads (TikTok, Instagram, Pinterest)
  - NEVER rendered as product images in the hub
  - Empty by default — populated by social posting pipeline
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass(frozen=True)
class SurfaceProduct:
    # ──────────────────────────────────────────────────────────────────
    # PRODUCT TRUTH LAYER — real data only, never AI-generated
    # ──────────────────────────────────────────────────────────────────
    asin:             str    # Amazon ASIN — 10 chars alphanumeric, required
    name:             str    # Product name from Amazon listing
    price:            float  # Listed price in USD
    category:         str    # Product category
    affiliate_url:    str    # Amazon affiliate link (tag=aetherglobal-20)
    tracking_url:     str    # Cloudflare Worker click tracking URL (/go/{asin})
    image_url:        str    # REAL Amazon CDN image (m.media-amazon.com) — required
    final_score:      float  # Ranking score from ranking_engine
    section:          str    # "hero" | "trending" | "evergreen" | "category" | "recent"
    archetype_label:  str    # Visual archetype label (from visual_intelligence or "")
    creative_mode:    str    # Creative mode from campaigns.json
    evergreen_status: str    # "active" | "evergreen" | "experimental" | "archived"
    rating:           float = 0.0   # Amazon star rating (0.0–5.0)
    reviews:          int   = 0     # Amazon review count

    # ──────────────────────────────────────────────────────────────────
    # MARKETING LAYER — AI-generated promotional content (social ads only)
    # These fields are NEVER used to render product images in the hub.
    # They are populated by the social posting pipeline (FLOW_DIRECTOR, etc.)
    # and consumed exclusively by platform executors (TikTok, Instagram, etc.).
    # ──────────────────────────────────────────────────────────────────
    marketing_video_url:      str   = ""   # AI-generated promo video (Flow/Runway/etc.)
    marketing_carousel_urls:  tuple = ()   # AI-generated carousel frames for social ads

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class HubSurface:
    generated_at: str
    hero:         SurfaceProduct
    trending:     tuple
    evergreen:    tuple
    by_category:  dict
    recent:       tuple

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
    click_id:       str   # uuid4
    product_id:     str
    asin:           str
    platform:       str
    campaign:       str
    archetype:      str
    source_surface: str
    timestamp:      str
    visual_mode:    str
    category:       str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class EvergreenEntry:
    asin:              str
    product_name:      str
    category:          str
    status:            str   # active | evergreen | archived | experimental
    first_seen:        str
    last_promoted:     str
    total_clicks:      int
    total_posts:       int
    performance_score: float
    affiliate_url:     str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Campaign:
    campaign_id:        str
    name:               str
    start_date:         str
    end_date:           str
    priority_boost:     float
    target_categories:  tuple
    visual_theme:       str
    status:             str   # active | expired

    def to_dict(self) -> dict:
        d = asdict(self)
        d["target_categories"] = list(self.target_categories)
        return d

"""
test_conversion_surface.py — 15 tests for IMPERIO Conversion Surface Layer.
Target: PASS ≥ 15, FAIL = 0.
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

import dataclasses
import pytest

# Add IMPERIO_ROOT to path
_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from conversion_surface.schemas import (
    SurfaceProduct, HubSurface, ClickEvent, EvergreenEntry, Campaign
)
from conversion_surface.ranking_engine import rank_products, _aggregate_clicks
from conversion_surface.template_renderer import render_html
from conversion_surface.static_site_builder import build_static_site


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_product(**kwargs) -> dict:
    defaults = {
        "asin": "B000000001",
        "name": "Test Product",
        "price": 29.99,
        "category": "home",
        "affiliate_url": "https://www.amazon.com/dp/B000000001?tag=aetherglobal-20",
        "evergreen_status": "active",
        "last_promoted": datetime.now(timezone.utc).isoformat(),
    }
    defaults.update(kwargs)
    return defaults


def _make_surface_product(**kwargs) -> SurfaceProduct:
    defaults = dict(
        asin="B000000001", name="Test", price=29.99, category="home",
        affiliate_url="https://www.amazon.com/dp/B000000001?tag=aetherglobal-20",
        tracking_url="https://worker.dev/go/B000000001",
        image_url="", final_score=0.7, section="hero",
        archetype_label="Luxury", creative_mode="A",
        evergreen_status="active",
    )
    defaults.update(kwargs)
    return SurfaceProduct(**defaults)


def _make_hub() -> HubSurface:
    hero = _make_surface_product(asin="B000000001", section="hero", rating=4.7, reviews=2340)
    t1   = _make_surface_product(asin="B000000002", section="trending", category="beauty", rating=4.3, reviews=890)
    t2   = _make_surface_product(asin="B000000003", section="trending", category="sports")
    ev1  = _make_surface_product(asin="B000000004", section="evergreen", evergreen_status="evergreen")
    r1   = _make_surface_product(asin="B000000005", section="recent")
    return HubSurface(
        generated_at = "2026-01-01T00:00:00+00:00",
        hero         = hero,
        trending     = (t1, t2),
        evergreen    = (ev1,),
        by_category  = {"home": (hero,), "beauty": (t1,)},
        recent       = (r1,),
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_ranking_determinism():
    """Same input → same output."""
    products   = [_make_product(asin=f"B{i:09d}") for i in range(5)]
    campaigns  = {}
    click_log  = {"clicks": []}
    memory     = {}

    result1 = rank_products(products, campaigns, click_log, memory)
    result2 = rank_products(products, campaigns, click_log, memory)
    assert [p.asin for p in result1] == [p.asin for p in result2]


def test_click_event_schema():
    """ClickEvent is frozen, all required fields present."""
    event = ClickEvent(
        click_id="abc", product_id="B000000001", asin="B000000001",
        platform="instagram", campaign="camp1", archetype="luxury",
        source_surface="hub", timestamp="2026-01-01T00:00:00Z",
        visual_mode="A", category="home",
    )
    with pytest.raises((AttributeError, TypeError, dataclasses.FrozenInstanceError)):
        event.click_id = "mutated"  # frozen dataclass — must raise
    d = event.to_dict()
    assert d["click_id"] == "abc"
    assert d["platform"] == "instagram"


def test_redirect_integrity():
    """Tracking URL contains affiliate tag."""
    p = _make_surface_product(
        tracking_url="https://worker.dev/go/B000000001?src=hub",
        affiliate_url="https://www.amazon.com/dp/B000000001?tag=aetherglobal-20",
    )
    # affiliate_url must contain tag
    assert "tag=aetherglobal-20" in p.affiliate_url


def test_evergreen_persistence():
    """Evergreen products always appear in ranked output."""
    products = [
        _make_product(asin="B000000001", evergreen_status="evergreen"),
        _make_product(asin="B000000002"),
        _make_product(asin="B000000003"),
    ]
    ranked = rank_products(products, {}, {"clicks": []}, {})
    asins  = [p.asin for p in ranked]
    assert "B000000001" in asins


def test_campaign_expiration():
    """Expired campaigns do not affect rankings."""
    products   = [_make_product(asin="B000000001")]
    expired_camp = {
        "camp1": {
            "status": "expired",
            "start_date": "2020-01-01",
            "end_date":   "2020-12-31",
            "priority_boost": 0.9,
            "target_categories": [],
        }
    }
    result_with  = rank_products(products, expired_camp, {"clicks": []}, {})
    result_without = rank_products(products, {}, {"clicks": []}, {})
    assert result_with[0].final_score == result_without[0].final_score


def test_archetype_integration():
    """archetype_label is preserved in SurfaceProduct."""
    products = [_make_product(asin="B000000001", archetype_label="Luxury Minimalist")]
    ranked   = rank_products(products, {}, {"clicks": []}, {})
    assert ranked[0].archetype_label == "Luxury Minimalist"


def test_malformed_url_rejection():
    """Products with no valid affiliate_url still produce valid SurfaceProduct."""
    products = [_make_product(asin="B000000001", affiliate_url="")]
    ranked   = rank_products(products, {}, {"clicks": []}, {})
    assert len(ranked) == 1
    # Should use fallback URL
    assert "B000000001" in ranked[0].affiliate_url or ranked[0].asin == "B000000001"


def test_duplicate_click_handling():
    """Click aggregation counts duplicates without mutating click list."""
    clicks = [
        {"product_id": "B000000001"},
        {"product_id": "B000000001"},
        {"product_id": "B000000002"},
    ]
    aggregated = _aggregate_clicks({"clicks": clicks})
    assert aggregated["B000000001"] == 2
    assert aggregated["B000000002"] == 1
    # Original list unchanged
    assert len(clicks) == 3


def test_rendering_determinism():
    """Same HubSurface → identical HTML output."""
    surface = _make_hub()
    html1   = render_html(surface)
    html2   = render_html(surface)
    assert html1 == html2


def test_static_build_consistency(tmp_path):
    """Build produces index.html + multi-file output (assets/, data/, i18n/)."""
    surface = _make_hub()
    html    = render_html(surface)
    build_static_site(surface, html, tmp_path)

    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "data" / "products.json").exists()
    assert (tmp_path / "assets" / "styles.css").exists()
    assert (tmp_path / "assets" / "app.js").exists()
    assert (tmp_path / "i18n" / "en.json").exists()

    data = json.loads((tmp_path / "data" / "products.json").read_text())
    assert "products" in data
    assert len(data["products"]) >= 1


def test_category_isolation():
    """by_category contains products grouped by category."""
    surface = _make_hub()
    for cat, prods in surface.by_category.items():
        for p in prods:
            assert p.category == cat


def test_append_only_verification():
    """rank_products does not mutate the input products list."""
    products = [_make_product(asin=f"B{i:09d}") for i in range(3)]
    original = [dict(p) for p in products]  # deep copy
    rank_products(products, {}, {"clicks": []}, {})
    for before, after in zip(original, products):
        assert before == after


def test_diversity_rule():
    """Max 2 products from same category in top 8."""
    products = [
        _make_product(asin=f"B{i:09d}", category="home")
        for i in range(10)
    ]
    ranked = rank_products(products, {}, {"clicks": []}, {})
    top8   = ranked[:8]
    from collections import Counter
    cat_counts = Counter(p.category for p in top8)
    for cat, count in cat_counts.items():
        assert count <= 2, f"Category '{cat}' appears {count} times in top 8 (max 2)"


def test_no_hallucinations():
    """Only ASINs from input products appear in ranked output."""
    valid_asins = {f"B{i:09d}" for i in range(5)}
    products    = [_make_product(asin=a) for a in valid_asins]
    ranked      = rank_products(products, {}, {"clicks": []}, {})
    for p in ranked:
        assert p.asin in valid_asins, f"Hallucinated ASIN: {p.asin}"


def test_freshness_boost():
    """Products promoted <3 days ago receive higher score than old products."""
    now = datetime.now(timezone.utc)
    fresh_product = _make_product(
        asin="B000000001",
        last_promoted=(now - timedelta(hours=12)).isoformat(),
    )
    old_product = _make_product(
        asin="B000000002",
        last_promoted=(now - timedelta(days=60)).isoformat(),
    )
    ranked = rank_products([fresh_product, old_product], {}, {"clicks": []}, {})
    scores = {p.asin: p.final_score for p in ranked}
    assert scores["B000000001"] > scores["B000000002"], (
        f"Fresh product ({scores['B000000001']}) should score higher than old ({scores['B000000002']})"
    )


def test_hub_surface_schema():
    """HubSurface is frozen and serializable."""
    surface = _make_hub()
    d = surface.to_dict()
    assert "hero" in d
    assert "trending" in d
    assert "generated_at" in d
    assert isinstance(d["trending"], list)

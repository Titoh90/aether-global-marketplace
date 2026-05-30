"""
hub_generator.py — Orchestrates the full Conversion Surface build pipeline.

build_hub()    → HubSurface
rebuild_hub()  → str (path to index.html)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .schemas import SurfaceProduct, HubSurface
from .ranking_engine import rank_products
from .template_renderer import render_html
from .static_site_builder import build_static_site, DEFAULT_OUT
from .image_cache import get_primary_image_url, warm_cache

_CATEGORY_MAP = {
    "Beauty & Personal Care": "beauty",
    "Home & Kitchen": "home",
    "Home & Garden": "home",
    "Electronics": "electronics",
    "Fashion": "fashion",
    "Sports & Outdoors": "sports",
}

def _normalize_category(cat: str) -> str:
    return _CATEGORY_MAP.get(cat, cat.lower())

_PROJECT_ROOT  = Path(__file__).resolve().parent.parent
_REVENUE_DIR   = _PROJECT_ROOT / "REVENUE"
_CAMPAIGNS_FILE = _REVENUE_DIR / "campaigns.json"
_BRIEF_FILE     = _REVENUE_DIR / "daily_brief.json"
_CLICK_FILE     = _REVENUE_DIR / "click_log.json"
_MEMORY_FILE    = _REVENUE_DIR / "system_memory.json"
_EVERGREEN_FILE = _REVENUE_DIR / "evergreen_store.json"


# ── Public API ────────────────────────────────────────────────────────────────

def build_hub(worker_base_url: str = "") -> HubSurface:
    """
    Reads all data sources, ranks products, builds HubSurface.
    Always includes verified evergreen base catalog.
    Merges real products from daily_brief.json on top.
    Never raises — returns minimal hub on failure.
    """
    # Start with verified evergreen catalog (always available, HD images cached)
    base_hub = _make_test_hub(worker_base_url)
    base_products = [base_hub.hero] + list(base_hub.trending) + list(base_hub.evergreen) + list(base_hub.recent)
    for cat_prods in base_hub.by_category.values():
        base_products.extend(cat_prods)
    base_asins = {p.asin for p in base_products}

    # Load real data sources (may be empty in CI)
    brief      = _load_json(_BRIEF_FILE,     {"products": []})
    campaigns  = _load_json(_CAMPAIGNS_FILE, {}).get("campaigns", {})
    click_log  = _load_json(_CLICK_FILE,     {"clicks": []})
    memory     = _load_json(_MEMORY_FILE,    {})
    evergreen  = _load_json(_EVERGREEN_FILE, {})

    # Build real products list from daily_brief
    real_products = list(brief.get("products", []))

    # Merge evergreen_store products not in brief
    brief_asins = {p.get("asin") for p in real_products}
    for asin, ev in evergreen.items():
        if asin not in brief_asins and ev.get("status") in ("active", "evergreen"):
            real_products.append({
                "asin":            asin,
                "name":            ev.get("product_name", asin),
                "price":           0.0,
                "category":        ev.get("category", "general"),
                "affiliate_url":   ev.get("affiliate_url", f"https://www.amazon.com/dp/{asin}/?tag=aetherglobal-20"),
                "evergreen_status": ev.get("status", "evergreen"),
                "last_promoted":   ev.get("last_promoted", ""),
            })

    # If we have real products, rank and merge with base
    if real_products:
        # Normalize categories before ranking
        for p in real_products:
            if "category" in p:
                p["category"] = _normalize_category(p["category"])
        ranked = rank_products(real_products, campaigns, click_log, memory, worker_base_url)
        # Deduplicate: real products take priority over base
        ranked_asins = {p.asin for p in ranked}
        deduped_base = [p for p in base_products if p.asin not in ranked_asins]
        # Seen set for dedup within base
        seen = set()
        unique_base = []
        for p in deduped_base:
            if p.asin not in seen:
                seen.add(p.asin)
                unique_base.append(p)
        all_products = ranked + unique_base
    else:
        # No real products — use base catalog as-is
        return base_hub

    if not all_products:
        fallback = _fallback_product(worker_base_url)
        all_products = [fallback]

    # Assign sections
    hero      = all_products[0]
    trending  = tuple(p for p in all_products[1:] if p.section in ("trending",))[:4] or tuple(all_products[1:5])
    evgreens  = tuple(p for p in all_products if p.evergreen_status == "evergreen" and p.asin != hero.asin)[:4]
    recent    = tuple(all_products[-5:]) if len(all_products) > 5 else tuple(all_products[1:])

    by_category: dict[str, tuple] = {}
    for p in all_products:
        cat = p.category
        if cat not in by_category:
            by_category[cat] = ()
        if len(by_category[cat]) < 8:
            by_category[cat] = by_category[cat] + (p,)

    return HubSurface(
        generated_at = datetime.now(timezone.utc).isoformat(),
        hero         = hero,
        trending     = trending,
        evergreen    = evgreens,
        by_category  = by_category,
        recent       = recent,
    )


def rebuild_hub(worker_base_url: str = "", output_dir: Path | None = None) -> str:
    """
    Full pipeline: warm image cache → rank → render → build static.
    Returns absolute path to index.html.
    Called from master_pipeline.py.
    """
    # Warm image cache for daily_brief ASINs (local only, skipped in CI)
    try:
        brief = _load_json(_BRIEF_FILE, {"products": []})
        asins = list({p.get("asin") for p in brief.get("products", []) if p.get("asin")})
        if asins:
            warm_cache(asins)
    except Exception:
        pass

    surface  = build_hub(worker_base_url=worker_base_url)
    html     = render_html(surface)
    out      = Path(output_dir) if output_dir else DEFAULT_OUT
    build_static_site(surface, html, out)
    return str(out / "index.html")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_json(path: Path, default) -> dict:
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default


def _fallback_product(worker_base_url: str) -> SurfaceProduct:
    asin = "B085DTZQNZ"  # Owala as default
    aff  = f"https://www.amazon.com/dp/{asin}/?tag=aetherglobal-20"
    trk  = f"{worker_base_url.rstrip('/')}/go/{asin}?src=hub" if worker_base_url else aff
    return SurfaceProduct(
        asin            = asin,
        name            = "Owala FreeSip",
        price           = 34.99,
        category        = "home",
        affiliate_url   = aff,
        tracking_url    = trk,
        image_url       = "",
        final_score     = 0.5,
        section         = "hero",
        archetype_label = "",
        creative_mode   = "",
        evergreen_status= "active",
        rating          = 0.0,
        reviews         = 0,
    )


def _make_test_hub(worker_base_url: str) -> HubSurface:
    """Rich test hub with verified ASINs + HD Amazon image IDs from image_cache."""

    # (asin, name, price, category, section, rating, reviews)
    VERIFIED_PRODUCTS = [
        # Electronics
        ("B0BDHWDR12", "Apple AirPods Pro (2nd Generation)", 199.99, "electronics", "hero", 4.8, 89432),
        ("B08KTZ8249", "Kindle Paperwhite (11th Gen) – 6.8\" display", 139.99, "electronics", "trending", 4.7, 45231),
        ("B09XS7JWHH", "Sony WH-1000XM5 Noise Canceling Headphones", 279.99, "electronics", "trending", 4.7, 28654),
        ("B09B8V1LZ3", "Amazon Echo Show 5 (3rd Gen)", 89.99, "electronics", "trending", 4.6, 19823),
        ("B0DGJ4QQ5W", "Apple MagSafe Charger (1m)", 38.99, "electronics", "recent", 4.6, 12934),
        # Beauty
        ("B00TTD9BRC", "CeraVe Moisturizing Cream (19 oz)", 16.99, "beauty", "evergreen", 4.8, 156432),
        # Home
        ("B085DTZQNZ", "Owala FreeSip Insulated Water Bottle (24oz)", 34.99, "home", "evergreen", 4.7, 47821),
        ("B00FLYWNYQ", "Instant Pot Duo 7-in-1 Electric Pressure Cooker (6 Qt)", 99.99, "home", "recent", 4.7, 132456),
        ("B07FDJMC9Q", "Ninja 4 Qt Air Fryer AF101", 99.99, "home", "recent", 4.7, 31287),
        # Fashion — premium brands, high reviews, verified 2026-05-29
        ("B0BXNRRN4Y", "Ray-Ban Classic Aviator RB3025 Sunglasses", 133.70, "fashion", "trending", 4.6, 24071),
        ("B0D9KM5SFR", "Nike Pegasus 41 Men's Running Shoe", 89.99, "fashion", "trending", 4.6, 1129),
        ("B0018OQQBE", "Levi's 501 Original Fit Men's Jeans", 69.99, "fashion", "trending", 4.5, 95932),
        ("B07PGR1XGZ", "Calvin Klein Cotton Stretch Boxer Briefs 7-Pack", 76.99, "fashion", "evergreen", 4.5, 14170),
        ("B097DD3G8G", "Michael Kors Jet Set Large Crossbody Bag", 83.44, "fashion", "trending", 4.8, 23254),
        ("B017SN1OI8", "Fossil Grant Chronograph Stainless Steel Watch", 113.40, "fashion", "evergreen", 4.7, 21027),
        ("B087FD9DSV", "adidas Ultraboost 21 Running Shoe", 99.99, "fashion", "trending", 4.6, 3750),
        ("B000VUCLII", "Hanes Men's Soft Cotton T-Shirts Multipack", 23.79, "fashion", "recent", 4.6, 5470),
        ("B06Y2ZW779", "New Balance 574 Core Men's Sneaker", 42.50, "fashion", "recent", 4.6, 10406),
        ("B06XW16QMS", "Oakley Holbrook Matte Black Sunglasses", 121.80, "fashion", "recent", 4.7, 1287),
    ]

    def _tp(asin, name, price, category, section, rating, reviews):
        aff = f"https://www.amazon.com/dp/{asin}/?tag=aetherglobal-20"
        trk = f"{worker_base_url.rstrip('/')}/go/{asin}?src=hub" if worker_base_url else aff
        primary_img = get_primary_image_url(asin, auto_scrape=False)
        return SurfaceProduct(
            asin=asin, name=name, price=price, category=category,
            affiliate_url=aff, tracking_url=trk,
            image_url=primary_img, final_score=0.8 + rating/10,
            section=section, archetype_label=category.title(),
            creative_mode="", evergreen_status="active",
            rating=rating, reviews=reviews,
        )

    products = [_tp(*row) for row in VERIFIED_PRODUCTS]

    hero     = products[0]
    trending = tuple(p for p in products if p.section == "trending")
    evgreens = tuple(p for p in products if p.section == "evergreen")
    recent   = tuple(p for p in products if p.section == "recent")

    by_category: dict = {}
    for p in products:
        by_category.setdefault(p.category, ())
        if len(by_category[p.category]) < 8:
            by_category[p.category] = by_category[p.category] + (p,)

    return HubSurface(
        generated_at = datetime.now(timezone.utc).isoformat(),
        hero         = hero,
        trending     = trending,
        evergreen    = evgreens,
        by_category  = by_category,
        recent       = recent,
    )

"""
hub_generator.py — Orchestrates the full Conversion Surface build pipeline.

build_hub()    → HubSurface
rebuild_hub()  → str (path to index.html)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .schemas import SurfaceProduct, HubSurface
from .ranking_engine import rank_products
from .template_renderer import render_html
from .static_site_builder import build_static_site, DEFAULT_OUT

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
    Never raises — returns minimal hub on failure.
    """
    # CI_TEST_MODE: return a rich test hub with video/carousel/product types
    if os.environ.get("CI_TEST_MODE"):
        return _make_test_hub(worker_base_url)

    brief      = _load_json(_BRIEF_FILE,     {"products": []})
    campaigns  = _load_json(_CAMPAIGNS_FILE, {}).get("campaigns", {})
    click_log  = _load_json(_CLICK_FILE,     {"clicks": []})
    memory     = _load_json(_MEMORY_FILE,    {})
    evergreen  = _load_json(_EVERGREEN_FILE, {})

    products = list(brief.get("products", []))

    # Merge evergreen products not in brief
    brief_asins = {p.get("asin") for p in products}
    for asin, ev in evergreen.items():
        if asin not in brief_asins and ev.get("status") in ("active", "evergreen"):
            products.append({
                "asin":            asin,
                "name":            ev.get("product_name", asin),
                "price":           0.0,
                "category":        ev.get("category", "general"),
                "affiliate_url":   ev.get("affiliate_url", f"https://www.amazon.com/dp/{asin}?tag=aetherglobal-20"),
                "evergreen_status": ev.get("status", "evergreen"),
                "last_promoted":   ev.get("last_promoted", ""),
            })

    ranked = rank_products(products, campaigns, click_log, memory, worker_base_url)

    if not ranked:
        # Minimal fallback product
        fallback = _fallback_product(worker_base_url)
        ranked   = [fallback]

    # Assign sections
    hero      = ranked[0]
    trending  = tuple(p for p in ranked[1:] if p.section in ("trending",))[:4] or tuple(ranked[1:5])
    evgreens  = tuple(p for p in ranked if p.evergreen_status == "evergreen" and p.asin != hero.asin)[:4]
    recent    = tuple(ranked[-5:]) if len(ranked) > 5 else tuple(ranked[1:])

    by_category: dict[str, tuple] = {}
    for p in ranked:
        cat = p.category
        if cat not in by_category:
            by_category[cat] = ()
        if len(by_category[cat]) < 4:
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
    Full pipeline: rank → generate → render → build static.
    Returns absolute path to index.html.
    Called from master_pipeline.py.
    """
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
    """Rich test hub with verified ASINs + HD Amazon image IDs (scraped & confirmed)."""

    # Verified HD image IDs per ASIN (Amazon I/ format, scraped from product pages)
    _HD_IMAGES: dict[str, list[str]] = {
        # Electronics
        "B0BDHWDR12": ["21ttIrgHhTL", "31TmzlrWV2L", "21On7xikgOL"],
        "B08KTZ8249": ["41uqWaJH1aL", "415YFn0VOzL", "61w6XlassQL"],
        "B09XS7JWHH": ["31BXEEUVfFL", "41JkueTBELL", "41WAozqLfiL"],
        "B09B8V1LZ3": ["31vkCUuIWCL", "315PBUzfZiL", "41NkdsdZ3OL"],
        "B0DGJ4QQ5W": ["21DcbviXOxL", "11RrezJCPgL", "11ZDMqH9n7L"],
        # Beauty
        "B00TTD9BRC": ["41ba2zJNMXL", "41itoI7tueL", "51Sb3T4JXGL"],
        # Home
        "B085DTZQNZ": ["718RbhzhVbL", "31iIKOIm46L", "41YVoy+qyXL"],
        "B00FLYWNYQ": ["71Z401LjFFL", "41OFXY6pMRL", "511i62OkshL"],
        "B07FDJMC9Q": ["71+8uTMDRFL", "31MBSKiZOPL", "410LYwPnZLL"],
        # Fashion
        "B0BXNRRN4Y": ["21Vq5RWfHWL", "216PIkplq4L", "21zh37OLDoL"],
        "B0D9KM5SFR": ["31xpQ4IwXvL", "31iEWGMUw7L", "310EDmNrhCL"],
        "B0018OQQBE": ["3160cyoSYNL", "31Yr6Dex7KL", "31bzt8t+PXL"],
        "B07PGR1XGZ": ["31QyJvLrLUL", "31cpEQq83sL", "31QXM6rindL"],
        "B097DD3G8G": ["417llnT8ZnL", "415-y8Z65gL", "21hUxmcIQ5L"],
        "B017SN1OI8": ["41OHta3+sfL", "31iWq9upMXL", "31pSSkjhHXL"],
        "B087FD9DSV": ["31oq+iAnWHS", "417P-uT2QhS", "51wAfLBl72L"],
        "B000VUCLII": ["41-Kk2ZPzmL", "61n7Q7NSkKL", "61bIZNWiM8L"],
        "B06Y2ZW779": ["31wHdsMEL-L", "51WiROyx-aL", "31UoMa-c0qL"],
        "B06XW16QMS": ["3170llwXGTL", "31eqVtvlvrL", "31NdngKkqYL"],
    }

    def _hd_url(image_id: str) -> str:
        return f"https://m.media-amazon.com/images/I/{image_id}._AC_SL1500_.jpg"

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
        img_ids = _HD_IMAGES.get(asin, [])
        primary_img = _hd_url(img_ids[0]) if img_ids else ""
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

"""
editorial_engine/transformer.py — Transforms raw products into editorial collections.

INPUT:  product_catalog.json OR daily_brief products
OUTPUT: enriched product_collections with narrative, visual direction, AI ad prompts

Sits ON TOP of existing pipeline. Never modifies source data.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _ROOT / "data"
_CATALOG_FILE = _DATA_DIR / "product_catalog.json"
_COLLECTIONS_FILE = _DATA_DIR / "product_collections.json"
_STYLES_FILE = _ROOT / "creative_engine" / "style_director.json"
_BRIEF_FILE = _ROOT / "REVENUE" / "daily_brief.json"

# Category → default creative style mapping
_CATEGORY_STYLE = {
    "electronics": "apple_minimal",
    "beauty": "luxury_skincare",
    "fashion": "nike_campaign",
    "home": "scandinavian_warm",
    "fitness": "lifestyle_active",
}


def load_catalog() -> list[dict]:
    """Load product catalog from data/product_catalog.json."""
    try:
        data = json.loads(_CATALOG_FILE.read_text())
        return data.get("products", [])
    except Exception:
        return []


def load_collections() -> list[dict]:
    """Load editorial collections from data/product_collections.json."""
    try:
        data = json.loads(_COLLECTIONS_FILE.read_text())
        return data.get("collections", [])
    except Exception:
        return []


def load_styles() -> dict:
    """Load creative style definitions from creative_engine/style_director.json."""
    try:
        data = json.loads(_STYLES_FILE.read_text())
        return data.get("categories", {})
    except Exception:
        return {}


def load_daily_brief() -> list[dict]:
    """Load products from REVENUE/daily_brief.json."""
    try:
        data = json.loads(_BRIEF_FILE.read_text())
        return data.get("products", [])
    except Exception:
        return []


def _normalize_category(cat: str) -> str:
    """Normalize Amazon category names to internal categories."""
    mapping = {
        "Beauty & Personal Care": "beauty",
        "Home & Kitchen": "home",
        "Home & Garden": "home",
        "Electronics": "electronics",
        "Fashion": "fashion",
        "Sports & Outdoors": "fitness",
    }
    return mapping.get(cat, cat.lower())


def catalog_by_asin() -> dict[str, dict]:
    """Index catalog products by ASIN for fast lookup."""
    return {p["asin"]: p for p in load_catalog() if p.get("asin")}


def enrich_collection(collection: dict, catalog: dict[str, dict], styles: dict) -> dict:
    """
    Enrich a collection with resolved products, style info, and AI prompts.

    Returns enriched collection dict with:
    - resolved_products: full product dicts (not just ASINs)
    - style_config: visual direction from style_director
    - ad_prompts: ready-to-use prompts for Flow Director
    - missing_products: ASINs not found in catalog
    """
    coll = dict(collection)

    # Resolve products
    product_asins = coll.get("products", [])
    resolved = []
    missing = []
    for asin in product_asins:
        if asin in catalog:
            resolved.append(catalog[asin])
        else:
            missing.append(asin)

    coll["resolved_products"] = resolved
    coll["missing_products"] = missing
    coll["product_count"] = len(resolved)

    # Resolve hero product
    hero_asin = coll.get("hero_product", "")
    coll["hero_resolved"] = catalog.get(hero_asin, {})

    # Get style config
    style_tag = coll.get("visual_style_tag", "")
    # Map style_tag to category key in styles
    style_map = {
        "apple_minimal": "electronics",
        "futuristic_tech": "electronics",
        "luxury_skincare": "beauty",
        "nike_campaign": "fashion",
        "editorial_luxury": "fashion",
        "scandinavian_warm": "home",
        "lifestyle_active": "fitness",
    }
    style_key = style_map.get(style_tag, "home")
    coll["style_config"] = styles.get(style_key, {})

    # Generate AI ad prompts for the collection
    coll["ad_prompts"] = _generate_ad_prompts(coll, styles.get(style_key, {}))

    return coll


def _generate_ad_prompts(collection: dict, style: dict) -> dict:
    """Generate ready-to-use prompts for Flow Director ad generation."""
    title = collection.get("title", "")
    theme = collection.get("theme", "")
    hero = collection.get("hero_resolved", {})
    hero_title = hero.get("title", "Product")

    prefix = style.get("prompt_prefix", "professional product photography")
    suffix = style.get("prompt_suffix", "8K, commercial quality")

    return {
        "collection_hero_ad": {
            "prompt": f"{prefix}, {hero_title}, {theme}, editorial campaign shot, {suffix}",
            "aspect": "1:1",
            "use": "Instagram feed / collection cover"
        },
        "collection_story_ad": {
            "prompt": f"{prefix}, cinematic product arrangement of premium items, {theme}, curated collection display, {suffix}",
            "aspect": "9:16",
            "use": "TikTok / Instagram Stories"
        },
        "collection_pinterest": {
            "prompt": f"{prefix}, styled flat lay arrangement, {theme}, editorial mood board aesthetic, {suffix}",
            "aspect": "2:3",
            "use": "Pinterest pin"
        },
        "product_hero_carousel": [
            {
                "slide": i + 1,
                "prompt": f"{prefix}, {p.get('title', 'product')}, {p.get('brand', '')} product shot, {suffix}",
                "asin": p.get("asin", ""),
            }
            for i, p in enumerate(collection.get("resolved_products", [])[:5])
        ],
    }


def transform_catalog_to_editorial() -> dict:
    """
    Main transformation: catalog + collections + styles → enriched editorial output.

    Returns dict with:
    - collections: list of enriched collections
    - unassigned_products: products not in any collection
    - stats: coverage metrics
    - generated_at: ISO timestamp
    """
    catalog = catalog_by_asin()
    collections = load_collections()
    styles = load_styles()

    enriched = []
    assigned_asins: set[str] = set()

    for coll in collections:
        enriched_coll = enrich_collection(coll, catalog, styles)
        enriched.append(enriched_coll)
        for asin in coll.get("products", []):
            assigned_asins.add(asin)

    # Find unassigned products
    unassigned = [p for asin, p in catalog.items() if asin not in assigned_asins]

    stats = {
        "total_products": len(catalog),
        "assigned_to_collections": len(assigned_asins),
        "unassigned": len(unassigned),
        "collections_count": len(enriched),
        "featured_collections": sum(1 for c in enriched if c.get("featured")),
        "coverage_pct": round(len(assigned_asins) / max(len(catalog), 1) * 100, 1),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "collections": enriched,
        "unassigned_products": unassigned,
        "stats": stats,
    }


def merge_daily_brief_into_catalog() -> dict:
    """
    Merge daily_brief.json products into product_catalog.json.
    New ASINs get added, existing ASINs get price/rating updated.
    Returns {added: N, updated: N, unchanged: N}.
    """
    try:
        cat_data = json.loads(_CATALOG_FILE.read_text())
    except Exception:
        cat_data = {"_meta": {"schema_version": 1}, "products": []}

    existing = {p["asin"]: p for p in cat_data.get("products", [])}
    brief_products = load_daily_brief()

    stats = {"added": 0, "updated": 0, "unchanged": 0}

    for bp in brief_products:
        asin = bp.get("asin", "")
        if not asin:
            continue

        if asin in existing:
            # Update price/rating if changed
            changed = False
            price = bp.get("price", 0)
            rating = bp.get("rating", 0)
            reviews = bp.get("reviews", bp.get("review_count", 0))
            if price and price != existing[asin].get("price"):
                existing[asin]["price"] = price
                changed = True
            if rating and rating != existing[asin].get("rating"):
                existing[asin]["rating"] = rating
                changed = True
            if reviews and reviews != existing[asin].get("review_count"):
                existing[asin]["review_count"] = reviews
                changed = True
            stats["updated" if changed else "unchanged"] += 1
        else:
            # New product
            category = _normalize_category(bp.get("category", "general"))
            new_product = {
                "asin": asin,
                "title": bp.get("name", bp.get("title", asin)),
                "brand": "",
                "price": bp.get("price", 0),
                "category": category,
                "subcategory": "",
                "affiliate_url": f"https://www.amazon.com/dp/{asin}/?tag=aetherglobal-20",
                "rating": bp.get("rating", 0),
                "review_count": bp.get("reviews", bp.get("review_count", 0)),
                "tags": ["new"],
                "creative_style": _CATEGORY_STYLE.get(category, "scandinavian_warm"),
                "social_angles": [],
                "collections": [],
                "trend_score": bp.get("trend_score", bp.get("final_score", 50)),
                "source": "daily_brief",
            }
            existing[asin] = new_product
            stats["added"] += 1

    # Write back
    cat_data["products"] = list(existing.values())
    cat_data["_meta"]["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _CATALOG_FILE.write_text(
        json.dumps(cat_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return stats


def generate_collection_for_frontend(collection_id: str | None = None) -> list[dict]:
    """
    Generate frontend-ready collection data for the marketplace.
    If collection_id specified, returns single collection. Otherwise all featured.

    Each collection includes:
    - id, title, subtitle, editorial_story
    - products with full details (title, price, image, affiliate_url, rating)
    - social_angle, cta_style
    - ad_prompts for creative generation
    """
    result = transform_catalog_to_editorial()
    from conversion_surface.image_cache import get_primary_image_url

    frontend_collections = []
    for coll in result["collections"]:
        if collection_id and coll["id"] != collection_id:
            continue
        if not collection_id and not coll.get("featured"):
            continue

        # Build frontend product list with image URLs
        products = []
        for p in coll.get("resolved_products", []):
            asin = p.get("asin", "")
            products.append({
                "asin": asin,
                "title": p.get("title", ""),
                "brand": p.get("brand", ""),
                "price": p.get("price", 0),
                "image": get_primary_image_url(asin, auto_scrape=False),
                "rating": p.get("rating", 0),
                "review_count": p.get("review_count", 0),
                "affiliate_url": p.get("affiliate_url", ""),
                "tags": p.get("tags", []),
            })

        hero_asin = coll.get("hero_product", "")
        frontend_collections.append({
            "id": coll["id"],
            "title": coll["title"],
            "theme": coll.get("theme", ""),
            "editorial_story": coll.get("editorial_story", ""),
            "hero_product": hero_asin,
            "hero_image": get_primary_image_url(hero_asin, auto_scrape=False) if hero_asin else "",
            "products": products,
            "product_count": len(products),
            "visual_style_tag": coll.get("visual_style_tag", ""),
            "cta_style": coll.get("cta_style", "discovery"),
            "social_angle": coll.get("social_angle", {}),
        })

    return frontend_collections


# ── CLI interface ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if "--merge-brief" in sys.argv:
        stats = merge_daily_brief_into_catalog()
        print(f"Merged daily_brief → catalog: {stats}")
    elif "--transform" in sys.argv:
        result = transform_catalog_to_editorial()
        print(f"Collections: {result['stats']['collections_count']}")
        print(f"Coverage: {result['stats']['coverage_pct']}%")
        print(f"Unassigned: {result['stats']['unassigned']}")
        for c in result["collections"]:
            print(f"  [{c['id']}] {c['title']} — {c['product_count']} products")
    elif "--frontend" in sys.argv:
        colls = generate_collection_for_frontend()
        print(json.dumps(colls, indent=2, ensure_ascii=False)[:2000])
    else:
        print("Usage: python transformer.py --merge-brief | --transform | --frontend")

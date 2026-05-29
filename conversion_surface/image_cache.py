"""
image_cache.py — Persistent HD image ID cache for Amazon products.

Stores verified hiRes image IDs (Amazon I/ format) per ASIN.
Auto-populated by scraping Amazon product pages when new ASINs appear.
Falls back to P/ format (160x160) for ASINs that can't be scraped.

Cache file: IMPERIO_ROOT/REVENUE/product_image_cache.json
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).resolve().parent.parent
_CACHE_FILE = _IMPERIO_ROOT / "REVENUE" / "product_image_cache.json"

# Seed cache — verified hiRes IDs scraped from Amazon (2026-05-29)
_SEED_CACHE: dict[str, list[str]] = {
    # Electronics
    "B0BDHWDR12": ["61f1YfTkTDL", "617I3mDGmTL", "51OoKCakCfL"],
    "B08KTZ8249": ["61P+vrvFZ9L", "51QCk82iGcL", "71d6+Ib9muL"],
    "B09XS7JWHH": ["61vJtKbAssL", "51QbrLdao0L", "81V1VCLb4oL"],
    "B09B8V1LZ3": ["61J2sQtBYDL", "71hNp8d9WvL", "71kDL97LTgL"],
    "B0DGJ4QQ5W": ["61QQUuYtWNL", "515oIieSmnL", "51yI62DIDmL"],
    # Beauty
    "B00TTD9BRC": ["61EidjXUBrL", "61-Ut3jOyyL", "91cwHnwUVEL"],
    # Home
    "B085DTZQNZ": ["718RbhzhVbL", "51B4ZbLNkOL", "512t1wfCMZL"],
    "B00FLYWNYQ": ["71Z401LjFFL", "91V5r8X2VgL", "81s0Ow2f6sL"],
    "B07FDJMC9Q": ["71+8uTMDRFL", "71wDCEfqZlL", "917o1KllOxL"],
    # Fashion
    "B0BXNRRN4Y": ["51+YqqbWIML", "513yiRQ4xwL", "51DXz1+d1mL"],
    "B0D9KM5SFR": ["61WTJldtvgL", "61yUyjhKsLL", "71YkzMrd6ZL"],
    "B0018OQQBE": ["41NgDv59BaL", "51WtUkd+bDL", "61ERUtlEPGL"],
    "B07PGR1XGZ": ["51wCTS-vHXL", "717P2-hKtoL", "61D4PlHJmGL"],
    "B097DD3G8G": ["71G65R-XC2L", "71dhTScRQgL", "61JRJjqnzSL"],
    "B017SN1OI8": ["818lBoWqXtL", "61V+is+XpkL", "61dh4J4f8ML"],
    "B087FD9DSV": ["61PGo56GK5S", "71a9nX2lPAS", "61IwyWsyO5S"],
    "B000VUCLII": ["61bIZNWiM8L"],
    "B06Y2ZW779": ["81j9yqr0R9L", "91+8pVW0mPL", "71Oe8HH5g2L"],
    "B06XW16QMS": ["618RD2rf+UL", "511cl6-GKkL", "51GEvpRPsUL"],
}

_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]


def _load_cache() -> dict[str, list[str]]:
    """Load cache from disk, merging with seed data."""
    cache = dict(_SEED_CACHE)
    try:
        if _CACHE_FILE.exists():
            disk = json.loads(_CACHE_FILE.read_text())
            if isinstance(disk, dict):
                cache.update(disk)
    except Exception:
        pass
    return cache


def _save_cache(cache: dict[str, list[str]]) -> None:
    """Persist cache to disk."""
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(
            json.dumps(cache, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _scrape_hires_ids(asin: str) -> list[str]:
    """
    Scrape hiRes image IDs from Amazon product page.
    Extracts from colorImages JSON and data-old-hires attribute.
    Returns list of image IDs or empty list on failure.
    """
    url = f"https://www.amazon.com/dp/{asin}/"
    ua = _USER_AGENTS[hash(asin) % len(_USER_AGENTS)]

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            # Read in chunks to handle large pages
            data = resp.read(500_000)
            html = data.decode("utf-8", errors="replace")
    except Exception:
        return []

    # Extract hiRes image IDs from colorImages/ImageBlockATF data
    ids: list[str] = []
    for match in re.finditer(r'"hiRes"\s*:\s*"https://m\.media-amazon\.com/images/I/([A-Za-z0-9+_-]+)\.', html):
        img_id = match.group(1)
        if img_id not in ids:
            ids.append(img_id)

    # Also check data-old-hires attribute on landing image
    hires_match = re.search(r'data-old-hires="https://m\.media-amazon\.com/images/I/([A-Za-z0-9+_-]+)\.', html)
    if hires_match:
        img_id = hires_match.group(1)
        if img_id not in ids:
            ids.insert(0, img_id)

    return ids[:5]


def hd_image_url(image_id: str) -> str:
    """Build full Amazon CDN HD URL from image ID."""
    return f"https://m.media-amazon.com/images/I/{image_id}._AC_SL1500_.jpg"


def get_image_ids(asin: str, auto_scrape: bool = True) -> list[str]:
    """
    Get HD image IDs for an ASIN.
    Checks cache first, scrapes Amazon if not found and auto_scrape=True.
    """
    cache = _load_cache()

    if asin in cache and cache[asin]:
        return cache[asin]

    if not auto_scrape:
        return []

    # Scrape and cache
    ids = _scrape_hires_ids(asin)
    if ids:
        cache[asin] = ids
        _save_cache(cache)

    return ids


def get_primary_image_url(asin: str, auto_scrape: bool = True) -> str:
    """
    Get the best available image URL for an ASIN.
    Returns hiRes URL if available, falls back to P/ format.
    """
    ids = get_image_ids(asin, auto_scrape=auto_scrape)
    if ids:
        return hd_image_url(ids[0])
    # Fallback — P/ format returns 160x160 but better than nothing
    return f"https://m.media-amazon.com/images/P/{asin}.01._SL1500_.jpg"


def get_carousel_urls(asin: str, auto_scrape: bool = True) -> list[str]:
    """Get up to 3 HD image URLs for carousel display."""
    ids = get_image_ids(asin, auto_scrape=auto_scrape)
    if ids:
        return [hd_image_url(img_id) for img_id in ids[:3]]
    primary = get_primary_image_url(asin, auto_scrape=False)
    return [primary] if primary else []


def warm_cache(asins: list[str]) -> dict[str, int]:
    """
    Pre-populate cache for a list of ASINs.
    Returns {cached: N, scraped: N, failed: N}.
    """
    cache = _load_cache()
    stats = {"cached": 0, "scraped": 0, "failed": 0}

    for asin in asins:
        if asin in cache and cache[asin]:
            stats["cached"] += 1
            continue
        ids = _scrape_hires_ids(asin)
        if ids:
            cache[asin] = ids
            stats["scraped"] += 1
        else:
            stats["failed"] += 1

    _save_cache(cache)
    return stats

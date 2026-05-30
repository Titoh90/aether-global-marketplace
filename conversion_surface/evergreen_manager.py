"""
evergreen_manager.py — Persistent product memory across campaigns.

Storage: REVENUE/evergreen_store.json
Rules:
  - record_product(): upsert entry
  - promote_to_evergreen(): req: ≥3 posts AND performance_score ≥60
  - archive(): status → "archived" (manual only — never auto-delete)
  - get_active_evergreens(): returns status in ("active", "evergreen")
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .schemas import EvergreenEntry

REVENUE_DIR    = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE")
EVERGREEN_FILE = REVENUE_DIR / "evergreen_store.json"

_lock = threading.Lock()


# ── Public API ────────────────────────────────────────────────────────────────

def record_product(
    asin: str,
    product_name: str,
    category: str,
    affiliate_url: str,
    posts_delta: int = 1,
    clicks_delta: int = 0,
    performance_score: float = 0.0,
) -> EvergreenEntry:
    """Upsert product in evergreen store. Returns updated entry."""
    store = _load()
    now   = datetime.now(timezone.utc).isoformat()

    existing = store.get(asin)
    if existing:
        entry = EvergreenEntry(
            asin             = asin,
            product_name     = product_name or existing["product_name"],
            category         = category or existing["category"],
            status           = existing.get("status", "active"),
            first_seen       = existing["first_seen"],
            last_promoted    = now,
            total_clicks     = existing.get("total_clicks", 0) + clicks_delta,
            total_posts      = existing.get("total_posts", 0) + posts_delta,
            performance_score= max(performance_score, existing.get("performance_score", 0.0)),
            affiliate_url    = affiliate_url or existing["affiliate_url"],
        )
    else:
        entry = EvergreenEntry(
            asin             = asin,
            product_name     = product_name,
            category         = category,
            status           = "active",
            first_seen       = now,
            last_promoted    = now,
            total_clicks     = clicks_delta,
            total_posts      = posts_delta,
            performance_score= performance_score,
            affiliate_url    = affiliate_url,
        )

    store[asin] = entry.to_dict()
    _save(store)
    return entry


def promote_to_evergreen(asin: str) -> bool:
    """
    Promote product to evergreen status.
    Requires: ≥3 posts AND performance_score ≥60.
    Returns True if promoted, False if requirements not met.
    """
    store = _load()
    entry = store.get(asin)
    if not entry:
        return False
    if entry.get("total_posts", 0) < 3:
        return False
    if entry.get("performance_score", 0.0) < 60.0:
        return False
    store[asin]["status"] = "evergreen"
    _save(store)
    return True


def archive(asin: str) -> bool:
    """Set status → archived. Manual only. Returns True if found."""
    store = _load()
    if asin not in store:
        return False
    store[asin]["status"] = "archived"
    _save(store)
    return True


def get_active_evergreens() -> list[EvergreenEntry]:
    """Returns all entries with status in ('active', 'evergreen')."""
    store = _load()
    result = []
    for asin, data in store.items():
        if data.get("status", "active") in ("active", "evergreen"):
            result.append(EvergreenEntry(**data))
    return result


def get_all() -> dict[str, dict]:
    """Return raw store dict."""
    return _load()


# ── Storage ───────────────────────────────────────────────────────────────────

def _load() -> dict:
    with _lock:
        if not EVERGREEN_FILE.exists():
            return {}
        try:
            return json.loads(EVERGREEN_FILE.read_text())
        except Exception:
            return {}


def _save(store: dict) -> None:
    with _lock:
        REVENUE_DIR.mkdir(parents=True, exist_ok=True)
        EVERGREEN_FILE.write_text(json.dumps(store, indent=2, ensure_ascii=False))

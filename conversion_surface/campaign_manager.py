"""
campaign_manager.py — Temporal campaign management for Conversion Surface.

Storage: REVENUE/surface_campaigns.json
Rules:
  - add_campaign(): create campaign
  - get_active_campaigns(): campaigns where today between start/end
  - expire_campaigns(): marks past campaigns as expired (append-only history)
  - get_priority_boost(): float boost for active campaigns
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .schemas import Campaign

REVENUE_DIR      = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE")
CAMPAIGNS_FILE   = REVENUE_DIR / "surface_campaigns.json"

_lock = threading.Lock()


# ── Public API ────────────────────────────────────────────────────────────────

def add_campaign(
    name: str,
    start_date: str,
    end_date: str,
    priority_boost: float = 0.1,
    target_categories: list[str] | None = None,
    visual_theme: str = "",
) -> Campaign:
    """Create and persist a new campaign. Returns Campaign dataclass."""
    campaigns = _load()
    cid = f"camp_{uuid.uuid4().hex[:8]}"
    c = Campaign(
        campaign_id        = cid,
        name               = name,
        start_date         = start_date,
        end_date           = end_date,
        priority_boost     = priority_boost,
        target_categories  = tuple(target_categories or []),
        visual_theme       = visual_theme,
        status             = "active",
    )
    campaigns[cid] = c.to_dict()
    _save(campaigns)
    return c


def get_active_campaigns() -> list[Campaign]:
    """Return campaigns where today is between start_date and end_date."""
    today = datetime.now(timezone.utc).date().isoformat()
    result = []
    for cid, data in _load().items():
        if data.get("status", "expired") != "active":
            continue
        if data.get("start_date", today) <= today <= data.get("end_date", today):
            cats = data.get("target_categories", [])
            c = Campaign(
                campaign_id        = cid,
                name               = data.get("name", ""),
                start_date         = data.get("start_date", ""),
                end_date           = data.get("end_date", ""),
                priority_boost     = data.get("priority_boost", 0.0),
                target_categories  = tuple(cats),
                visual_theme       = data.get("visual_theme", ""),
                status             = "active",
            )
            result.append(c)
    return result


def expire_campaigns() -> int:
    """Mark past campaigns as expired. Append-only — never delete. Returns count expired."""
    today = datetime.now(timezone.utc).date().isoformat()
    campaigns = _load()
    count = 0
    for cid, data in campaigns.items():
        if data.get("status") == "active" and data.get("end_date", today) < today:
            campaigns[cid]["status"] = "expired"
            count += 1
    if count:
        _save(campaigns)
    return count


def get_priority_boost(asin: str, category: str) -> float:
    """Return max priority_boost from active campaigns for this asin/category."""
    today = datetime.now(timezone.utc).date().isoformat()
    best  = 0.0
    for c in get_active_campaigns():
        cats = list(c.target_categories)
        if not cats or category in cats or asin in cats:
            best = max(best, c.priority_boost)
    return best


# ── Storage ───────────────────────────────────────────────────────────────────

def _load() -> dict:
    with _lock:
        if not CAMPAIGNS_FILE.exists():
            return {}
        try:
            return json.loads(CAMPAIGNS_FILE.read_text())
        except Exception:
            return {}


def _save(campaigns: dict) -> None:
    with _lock:
        REVENUE_DIR.mkdir(parents=True, exist_ok=True)
        CAMPAIGNS_FILE.write_text(json.dumps(campaigns, indent=2, ensure_ascii=False))

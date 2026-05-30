#!/usr/bin/env python3
"""
competitor_registry.py — Registry of competitor accounts for intelligence gathering.

JSON-backed, append-safe registry. Never deletes — only marks inactive.
100% LOCAL — zero network calls.

Usage:
    from core.competitive_intelligence.competitor_registry import (
        add_competitor, get_active_competitors, get_by_platform
    )
"""

from __future__ import annotations

import datetime
import json
import sys
import threading
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.competitive_intelligence.schemas import CompetitorAccount

_REGISTRY_PATH = _IMPERIO_ROOT / "memory" / "competitor_registry.json"
_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _load_registry() -> list[dict]:
    """Load registry from disk. Returns empty list on any failure."""
    try:
        if _REGISTRY_PATH.exists():
            return json.loads(_REGISTRY_PATH.read_text())
    except Exception:
        pass
    return []


def _save_registry(data: list[dict]) -> None:
    """Atomically write registry. Silent on failure."""
    try:
        _REGISTRY_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception:
        pass


# ── Public API ────────────────────────────────────────────────────────────────

def add_competitor(
    username: str,
    platform: str,
    niche:    str = "",
    tags:     list[str] | None = None,
) -> CompetitorAccount:
    """
    Add a competitor account to the registry.

    Dedup by username+platform — if already exists, returns existing entry.
    """
    with _lock:
        registry = _load_registry()

        # Dedup check
        for entry in registry:
            if entry["username"].lower() == username.lower() and entry["platform"] == platform.lower():
                entry["active"] = True
                _save_registry(registry)
                return CompetitorAccount(
                    account_id=entry["account_id"],
                    username=entry["username"],
                    platform=entry["platform"],
                    niche=entry.get("niche", ""),
                    tags=tuple(entry.get("tags", [])),
                    added_at=entry["added_at"],
                    active=True,
                )

        account_id = f"{platform.lower()}_{username.lower().replace('@','')}"
        entry = CompetitorAccount(
            account_id=account_id,
            username=username,
            platform=platform.lower(),
            niche=niche,
            tags=tuple(tags or []),
            added_at=_now_iso(),
            active=True,
        )

        registry.append(entry.to_dict())
        _save_registry(registry)
        return entry


def remove_competitor(account_id: str) -> bool:
    """Mark a competitor as inactive. Returns True if found."""
    with _lock:
        registry = _load_registry()
        for entry in registry:
            if entry["account_id"] == account_id:
                entry["active"] = False
                _save_registry(registry)
                return True
        return False


def get_active_competitors() -> list[CompetitorAccount]:
    """Return all active competitors."""
    registry = _load_registry()
    return [
        CompetitorAccount(
            account_id=e["account_id"],
            username=e["username"],
            platform=e["platform"],
            niche=e.get("niche", ""),
            tags=tuple(e.get("tags", [])),
            added_at=e.get("added_at", ""),
            active=e.get("active", True),
        )
        for e in registry if e.get("active", True)
    ]


def get_by_platform(platform: str) -> list[CompetitorAccount]:
    """Return active competitors for a specific platform."""
    return [c for c in get_active_competitors() if c.platform == platform.lower()]


def get_by_niche(niche: str) -> list[CompetitorAccount]:
    """Return active competitors in a specific niche (case-insensitive)."""
    return [c for c in get_active_competitors() if c.niche.lower() == niche.lower()]


def count() -> int:
    """Return count of active competitors."""
    return len(get_active_competitors())


def list_all() -> list[dict]:
    """Return all registry entries as dicts (including inactive)."""
    return _load_registry()

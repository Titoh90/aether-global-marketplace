#!/usr/bin/env python3
"""Safe inspiration metadata ingestion for Creative Intelligence."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from core.creative_intelligence.signal_store import IMPERIO_ROOT

ALLOWED_FIELDS = (
    "source",
    "style_type",
    "composition_structure",
    "hook_type",
    "cta_type",
    "palette_family",
    "engagement_pattern_type",
)


def _store_path(root: Path) -> Path:
    return Path(root) / "memory" / "creative_intelligence" / "inspiration_fingerprints.json"


def ingest_fingerprint(fingerprint: dict, root: Path = IMPERIO_ROOT) -> dict:
    """
    Store only structural metadata. Raw content, URLs, captions, and images are
    intentionally dropped.
    """
    clean = {field: str(fingerprint.get(field, "unknown") or "unknown") for field in ALLOWED_FIELDS}
    raw = "|".join(clean[field] for field in ALLOWED_FIELDS)
    clean["fingerprint_id"] = hashlib.sha256(raw.encode()).hexdigest()[:16]
    clean["ingested_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    path = _store_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text()) if path.exists() else {"fingerprints": []}
    except Exception:
        data = {"fingerprints": []}

    existing = {item.get("fingerprint_id") for item in data.get("fingerprints", [])}
    if clean["fingerprint_id"] not in existing:
        data.setdefault("fingerprints", []).append(clean)
        path.write_text(json.dumps(data, indent=2))
        return {"stored": True, "fingerprint_id": clean["fingerprint_id"]}
    return {"stored": False, "fingerprint_id": clean["fingerprint_id"], "reason": "duplicate"}

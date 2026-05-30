#!/usr/bin/env python3
"""
Creative Signal Store for HERMES Creative Brain v2.

Reads existing production artifacts and builds a unified creative state. The only
write this module performs is REVENUE/creative_intelligence_state.json.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text()) if path.exists() else default
    except Exception:
        return default


def _load_jsonl(path: Path, limit: int = 100) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        for line in path.read_text().splitlines()[-limit:]:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except Exception:
        return []
    return rows


def _campaigns(root: Path) -> dict[str, dict]:
    raw = _load_json(root / "REVENUE" / "campaigns.json", {})
    data = raw.get("campaigns", raw) if isinstance(raw, dict) else {}
    return data if isinstance(data, dict) else {}


def _latest_ci_report(root: Path) -> dict:
    ci_dir = root / "memory" / "competitive_intelligence"
    try:
        reports = sorted(ci_dir.glob("ci_report_*.json"))
    except Exception:
        return {}
    return _load_json(reports[-1], {}) if reports else {}


def _style_director(root: Path) -> dict:
    return _load_json(root / "creative_engine" / "style_director.json", {})


def _style_catalog(root: Path) -> dict[str, str]:
    categories = _style_director(root).get("categories", {})
    catalog: dict[str, str] = {}
    if isinstance(categories, dict):
        for category, data in categories.items():
            if isinstance(data, dict):
                catalog[category] = data.get("style_name", category)
    return catalog


def _campaign_summary(campaign_id: str, campaign: dict) -> dict:
    return {
        "campaign_id": campaign_id,
        "asin": campaign.get("asin", campaign_id),
        "product_name": campaign.get("product_name", campaign_id),
        "category": campaign.get("category", "general"),
        "phase": campaign.get("phase", "EXPLORATION"),
        "posts_count": int(campaign.get("posts_count", campaign.get("total_posts", 0)) or 0),
        "performance_score": float(campaign.get("performance_score", 0) or 0),
        "primary_mode": campaign.get("primary_mode", "UNKNOWN"),
        "secondary_modes": list(campaign.get("secondary_modes", []) or []),
        "hook_styles": list(campaign.get("hook_styles", []) or []),
        "visual_identity": campaign.get("visual_identity", {}) or {},
    }


def _risk_flags(root: Path, uck: dict, gdal: dict, brand: dict) -> list[dict]:
    flags: list[dict] = []
    for risk in gdal.get("stability_risks", []) or []:
        flags.append({"source": "gdal", "severity": "HIGH", "detail": str(risk)})
    for action in gdal.get("resolution_actions", []) or []:
        if isinstance(action, dict) and action.get("priority") in ("HIGH", "CRITICAL"):
            flags.append({"source": "gdal", "severity": action.get("priority"), "detail": action.get("detail", action.get("action", ""))})
    for product_id, output in (uck.get("outputs", {}) or {}).items():
        if isinstance(output, dict) and output.get("ready_to_publish") is False:
            flags.append({"source": "uck", "severity": "MEDIUM", "product_id": product_id, "detail": "Creative output not ready to publish"})
        for item in output.get("state_updates", {}).get("risk_flags", []) if isinstance(output, dict) else []:
            flags.append({"source": "uck", "severity": "MEDIUM", "product_id": product_id, "detail": str(item)})
    for item in brand.get("identity_risk_signals", []) or []:
        flags.append({"source": "brand", "severity": "MEDIUM", "detail": str(item)})
    return flags[:20]


def _warnings(campaigns: list[dict], style_usage: dict[str, int], brand: dict) -> list[str]:
    warnings: list[str] = []
    for style, count in sorted(style_usage.items(), key=lambda item: -item[1]):
        if count > 1:
            warnings.append(f"Repeated creative mode '{style}' across {count} campaigns")
    visual_score = brand.get("visual_consistency_score")
    if isinstance(visual_score, (int, float)) and visual_score < 65:
        warnings.append(f"Visual consistency low ({visual_score}/100): audit style drift")
    weak_campaigns = [c for c in campaigns if c.get("performance_score", 0) < 50 and c.get("posts_count", 0) >= 3]
    if weak_campaigns:
        warnings.append(f"{len(weak_campaigns)} campaigns show weak creative performance")
    return warnings[:10]


def _opportunities(root: Path, ci: dict, brand: dict, style_catalog: dict[str, str]) -> list[dict]:
    opportunities: list[dict] = []
    for item in brand.get("content_mix_adjustments", []) or []:
        if isinstance(item, dict) and item.get("action"):
            opportunities.append({"source": "brand", "detail": item["action"], "priority": item.get("priority", "MEDIUM")})
    for trend in ci.get("trends", []) or []:
        if isinstance(trend, dict):
            style = trend.get("style", "")
            if style and style != "unknown":
                opportunities.append({
                    "source": "competitive_intelligence",
                    "detail": f"Explore external style fingerprint '{style}'",
                    "priority": "MEDIUM",
                    "score": trend.get("viral_score", 0),
                })
    if style_catalog:
        opportunities.append({
            "source": "style_director",
            "detail": f"{len(style_catalog)} category style families available for rotation",
            "priority": "LOW",
        })
    return opportunities[:10]


def build_creative_signal_state(root: Path = IMPERIO_ROOT, persist: bool = True) -> dict:
    """
    Build the Creative Signal Core state.

    This function is read-only except for optional persistence to
    REVENUE/creative_intelligence_state.json.
    """
    root = Path(root)
    revenue = root / "REVENUE"
    campaign_map = _campaigns(root)
    campaign_list = [_campaign_summary(cid, c) for cid, c in campaign_map.items()]
    style_usage = Counter(c.get("primary_mode", "UNKNOWN") for c in campaign_list)
    hook_usage = Counter(h for c in campaign_list for h in c.get("hook_styles", []))

    engagement_rows = _load_jsonl(revenue / "engagement_shadow_log.jsonl")
    engagement_intents = Counter(str(row.get("intent", "unknown")) for row in engagement_rows)
    uck = _load_json(revenue / "uck_output.json", {})
    gdal = _load_json(revenue / "gdal_report.json", {})
    brand = _load_json(revenue / "brand_report.json", {})
    ci = _latest_ci_report(root)
    style_catalog = _style_catalog(root)

    state = {
        "version": 2,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "mode": "advisory",
        "sources": {
            "campaigns": len(campaign_list),
            "engagement_shadow": len(engagement_rows),
            "uck_outputs": len(uck.get("outputs", {}) or {}),
            "gdal_actions": len(gdal.get("resolution_actions", []) or []),
            "style_families": len(style_catalog),
            "ci_trends": len(ci.get("trends", []) or []),
        },
        "campaigns": campaign_list,
        "style_usage": dict(style_usage),
        "hook_usage": dict(hook_usage),
        "engagement_intents": dict(engagement_intents),
        "brand": {
            "visual_consistency_score": brand.get("visual_consistency_score"),
            "tone_consistency_score": brand.get("tone_consistency_score"),
            "identity_warning": brand.get("identity_warning", False),
        },
        "style_catalog": style_catalog,
        "risk_flags": _risk_flags(root, uck, gdal, brand),
        "warnings": _warnings(campaign_list, dict(style_usage), brand),
        "opportunities": _opportunities(root, ci, brand, style_catalog),
    }

    if persist:
        out = revenue / "creative_intelligence_state.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(state, indent=2, default=str))
    return state

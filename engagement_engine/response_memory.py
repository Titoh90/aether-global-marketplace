"""
response_memory.py — Track engagement response performance.

Learns what response styles generate more replies/likes.
Feeds back into response generation for adaptive optimization.
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

_ROOT = Path(__file__).resolve().parent.parent
_REVENUE = _ROOT / "REVENUE"
_MEMORY_FILE = _REVENUE / "engagement_memory.json"


def _load_memory() -> dict:
    try:
        if _MEMORY_FILE.exists():
            return json.loads(_MEMORY_FILE.read_text())
    except Exception:
        pass
    return {
        "intent_stats": {},
        "template_performance": {},
        "llm_performance": {},
        "response_rate_history": [],
        "updated": "",
    }


def _save_memory(data: dict) -> None:
    data["updated"] = datetime.now(timezone.utc).isoformat()
    try:
        _MEMORY_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def record_response(
    intent: str,
    method: str,
    response_text: str,
    status: str,
    category: str = "default",
) -> None:
    """Record a response event for future optimization."""
    mem = _load_memory()

    # Intent stats
    if intent not in mem["intent_stats"]:
        mem["intent_stats"][intent] = {
            "total": 0, "responded": 0, "skipped": 0, "errors": 0
        }
    stats = mem["intent_stats"][intent]
    stats["total"] += 1
    if status == "posted" or status == "shadow":
        stats["responded"] += 1
    elif status == "skipped":
        stats["skipped"] += 1
    elif status == "error":
        stats["errors"] += 1

    # Method performance
    method_key = f"{method}_performance"
    if method_key in mem:
        if category not in mem[method_key]:
            mem[method_key][category] = {"count": 0}
        mem[method_key][category]["count"] += 1

    # Response rate history (rolling window of 50)
    mem["response_rate_history"].append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "intent": intent,
        "status": status,
        "method": method,
    })
    mem["response_rate_history"] = mem["response_rate_history"][-50:]

    _save_memory(mem)


def get_stats() -> dict:
    """Get engagement stats summary."""
    mem = _load_memory()
    total = sum(s.get("total", 0) for s in mem.get("intent_stats", {}).values())
    responded = sum(s.get("responded", 0) for s in mem.get("intent_stats", {}).values())
    skipped = sum(s.get("skipped", 0) for s in mem.get("intent_stats", {}).values())

    return {
        "total_comments_processed": total,
        "responded": responded,
        "skipped": skipped,
        "response_rate": round(responded / max(total, 1), 2),
        "intent_breakdown": mem.get("intent_stats", {}),
        "last_updated": mem.get("updated", "never"),
    }

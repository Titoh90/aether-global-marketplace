"""
realtime_status.py — Real-time system status for Telegram.

Provides live status snapshots without running full observation cycle.
Lightweight — reads only the minimum files needed.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")


class RealtimeStatus:
    """Fast, lightweight system status reads."""

    def pipeline_status(self) -> dict:
        """Is pipeline running right now?"""
        lock = Path("/tmp/imperio-pipeline-master_pipeline.lock")
        if not lock.exists():
            return {"status": "idle", "pid": None}
        try:
            pid = int(lock.read_text().strip())
            os.kill(pid, 0)  # check alive
            return {"status": "running", "pid": pid}
        except (ValueError, ProcessLookupError, PermissionError):
            return {"status": "idle", "pid": None}

    def ai_spend(self) -> dict:
        """Current AI spend today."""
        today = time.strftime("%Y-%m-%d")
        spend_file = IMPERIO_ROOT / "logs" / "guardrails" / f"daily_spend_{today}.json"
        if not spend_file.exists():
            return {"total_usd": 0.0, "budget_usd": 0.0, "pct": 0.0}
        try:
            data = json.loads(spend_file.read_text())
            total = data.get("total_cost_usd", 0.0)
            budget = float(os.environ.get("IMPERIO_DAILY_AI_BUDGET_USD", "0") or "0")
            return {
                "total_usd": total,
                "budget_usd": budget,
                "pct": (total / budget * 100) if budget > 0 else 0.0,
            }
        except Exception:
            return {"total_usd": 0.0, "budget_usd": 0.0, "pct": 0.0}

    def circuit_breakers(self) -> dict[str, str]:
        """Current circuit breaker states."""
        cb_file = IMPERIO_ROOT / "logs" / "guardrails" / "circuit_breaker_state.json"
        if not cb_file.exists():
            return {}
        try:
            data = json.loads(cb_file.read_text())
            return {name: s.get("state", "CLOSED") for name, s in data.items()}
        except Exception:
            return {}

    def posts_today(self) -> int:
        """Quick count of posts today."""
        today = time.strftime("%Y-%m-%d")
        count = 0
        for log_name in ["instagram_posts.jsonl", "twitter_posts.jsonl",
                         "pinterest_posts.jsonl", "tiktok_posts.jsonl",
                         "posts_log.jsonl"]:
            log_path = IMPERIO_ROOT / "REVENUE" / log_name
            if log_path.exists():
                try:
                    with open(log_path) as f:
                        for line in f:
                            if today in line:
                                count += 1
                except Exception:
                    pass
        return count

    def is_paused(self) -> bool:
        """Check if pipeline is manually paused."""
        return (IMPERIO_ROOT / "logs" / "guardrails" / "pipeline_paused").exists()

    def snapshot(self) -> str:
        """Quick one-line status."""
        pipe = self.pipeline_status()
        posts = self.posts_today()
        spend = self.ai_spend()
        paused = self.is_paused()

        parts = [
            f"Pipeline:{pipe['status'].upper()}",
            f"Posts:{posts}",
            f"Spend:${spend['total_usd']:.3f}",
        ]
        if paused:
            parts.append("PAUSED")

        cbs = self.circuit_breakers()
        open_cbs = [k for k, v in cbs.items() if v == "OPEN"]
        if open_cbs:
            parts.append(f"CB_OPEN:{','.join(open_cbs)}")

        return " | ".join(parts)

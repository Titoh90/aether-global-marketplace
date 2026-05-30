"""
system_reader.py — Read ALL IMPERIO metrics in one snapshot.

Single source of truth for system state. Every reader is READ-ONLY.
Feeds into executive agent, reports, and Telegram responses.

Reads:
1. Affiliate performance (clicks, campaigns, revenue ledger)
2. Engagement stats (comments, responses)
3. Executor health (circuit breakers, posting safety)
4. Quality gate reports
5. AI spend
6. Pipeline status
7. Posting history
8. Trend data
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")


@dataclass
class SystemSnapshot:
    """Complete system state at a point in time."""
    timestamp: str

    # Pipeline
    pipeline_status: str
    pipeline_paused: bool

    # Posts
    posts_today: dict[str, int]  # {platform: count}
    total_posts_today: int

    # Failures
    failures_today: int
    recent_errors: list[str]

    # AI Spend
    ai_spend_usd: float
    ai_budget_usd: float
    ai_spend_pct: float

    # Affiliate
    clicks_today: int
    campaigns_active: int
    top_campaigns: list[dict]

    # Executor Health
    executor_states: dict[str, str]  # {executor: CLOSED|OPEN|HALF_OPEN}
    platform_health: dict[str, int]  # {platform: health_score}

    # Quality
    quality_scores: list[dict]

    # Engagement
    comments_today: int
    responses_today: int

    # Trends
    trending_products: list[str]

    # SSMIE
    ssmie_mode: str
    ssmie_protective: bool


class SystemReader:
    """Read-only access to all IMPERIO metrics."""

    def snapshot(self) -> SystemSnapshot:
        """Take complete system snapshot."""
        today = time.strftime("%Y-%m-%d")
        return SystemSnapshot(
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            pipeline_status=self._pipeline_status(),
            pipeline_paused=self._is_paused(),
            posts_today=self._posts_by_platform(today),
            total_posts_today=sum(self._posts_by_platform(today).values()),
            failures_today=self._count_failures(today),
            recent_errors=self._recent_errors(5),
            ai_spend_usd=self._ai_spend(today),
            ai_budget_usd=float(os.environ.get("IMPERIO_DAILY_AI_BUDGET_USD", "0") or "0"),
            ai_spend_pct=self._ai_spend_pct(today),
            clicks_today=self._clicks_today(today),
            campaigns_active=self._campaign_count(),
            top_campaigns=self._top_campaigns(5),
            executor_states=self._circuit_breakers(),
            platform_health=self._platform_health(),
            quality_scores=self._recent_quality(5),
            comments_today=self._engagement_count(today, "comments"),
            responses_today=self._engagement_count(today, "responses"),
            trending_products=self._trending(5),
            ssmie_mode=self._ssmie_mode(),
            ssmie_protective=self._ssmie_protective(),
        )

    def format_executive_summary(self, snap: SystemSnapshot = None) -> str:
        """Format snapshot as executive summary for Telegram."""
        if snap is None:
            snap = self.snapshot()

        lines = [
            "═══ IMPERIO EXECUTIVE SUMMARY ═══",
            f"  {snap.timestamp}",
            "",
            f"Pipeline: {snap.pipeline_status.upper()}" + (" (PAUSED)" if snap.pipeline_paused else ""),
            f"SSMIE: {snap.ssmie_mode}" + (" ⚠ PROTECTIVE" if snap.ssmie_protective else ""),
            "",
            "── Posts ──",
        ]
        for plat, count in snap.posts_today.items():
            lines.append(f"  {plat}: {count}")
        lines.append(f"  TOTAL: {snap.total_posts_today}")

        lines.append(f"\n── Fallos: {snap.failures_today} ──")
        if snap.recent_errors:
            for e in snap.recent_errors[:3]:
                lines.append(f"  • {e[:80]}")

        lines.append("\n── AI Spend ──")
        lines.append(f"  ${snap.ai_spend_usd:.4f}" + (
            f" ({snap.ai_spend_pct:.0f}% de ${snap.ai_budget_usd:.2f})"
            if snap.ai_budget_usd > 0 else " (sin budget)"))

        lines.append("\n── Affiliate ──")
        lines.append(f"  Clicks: {snap.clicks_today}")
        lines.append(f"  Campañas activas: {snap.campaigns_active}")
        if snap.top_campaigns:
            lines.append("  Top:")
            for c in snap.top_campaigns[:3]:
                lines.append(f"    {c['name'][:30]}: {c['posts']} posts")

        lines.append("\n── Executors ──")
        for ex, state in snap.executor_states.items():
            icon = {"CLOSED": "✅", "OPEN": "❌", "HALF_OPEN": "⚠️"}.get(state, "?")
            lines.append(f"  {icon} {ex}")
        if snap.platform_health:
            for plat, score in snap.platform_health.items():
                bar = "█" * (score // 10) + "░" * (10 - score // 10)
                lines.append(f"  {plat}: {bar} {score}/100")

        if snap.quality_scores:
            lines.append("\n── Quality Gate ──")
            for qs in snap.quality_scores[:3]:
                lines.append(f"  score={qs.get('score', '?')} {qs.get('pass_fail', '?')}")

        lines.append("\n── Engagement ──")
        lines.append(f"  Comments: {snap.comments_today} | Responses: {snap.responses_today}")

        if snap.trending_products:
            lines.append("\n── Trending ──")
            for t in snap.trending_products[:3]:
                lines.append(f"  • {t[:50]}")

        lines.append("\n═══════════════════════════════")
        return "\n".join(lines)

    # ── Individual Readers ─────────────────────────────────

    def _pipeline_status(self) -> str:
        lock = Path("/tmp/imperio-pipeline-master_pipeline.lock")
        if not lock.exists():
            return "idle"
        try:
            pid = int(lock.read_text().strip())
            os.kill(pid, 0)
            return "running"
        except (ValueError, ProcessLookupError, PermissionError):
            return "idle"

    def _is_paused(self) -> bool:
        return (IMPERIO_ROOT / "logs" / "guardrails" / "pipeline_paused").exists()

    def _posts_by_platform(self, today: str) -> dict[str, int]:
        counts = {}
        platform_logs = {
            "telegram": "posts_log.jsonl",
            "instagram": "instagram_posts.jsonl",
            "twitter": "twitter_posts.jsonl",
            "pinterest": "pinterest_posts.jsonl",
            "tiktok": "tiktok_posts.jsonl",
        }
        for plat, log_name in platform_logs.items():
            log_path = IMPERIO_ROOT / "REVENUE" / log_name
            if log_path.exists():
                try:
                    with open(log_path) as f:
                        counts[plat] = sum(1 for line in f if today in line)
                except Exception:
                    counts[plat] = 0
        return counts

    def _count_failures(self, today: str) -> int:
        events_file = IMPERIO_ROOT / "logs" / "events" / f"{today}.jsonl"
        if not events_file.exists():
            return 0
        try:
            with open(events_file) as f:
                return sum(1 for line in f if "failed" in line)
        except Exception:
            return 0

    def _recent_errors(self, limit: int) -> list[str]:
        today = time.strftime("%Y-%m-%d")
        events_file = IMPERIO_ROOT / "logs" / "events" / f"{today}.jsonl"
        if not events_file.exists():
            return []
        errors = []
        try:
            with open(events_file) as f:
                for line in f:
                    if "failed" in line or "error" in line.lower():
                        try:
                            entry = json.loads(line.strip())
                            et = entry.get("event_type", "unknown")
                            err = entry.get("data", {}).get("error", "")[:100]
                            errors.append(f"{et}: {err}" if err else et)
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass
        return errors[-limit:]

    def _ai_spend(self, today: str) -> float:
        f = IMPERIO_ROOT / "logs" / "guardrails" / f"daily_spend_{today}.json"
        if not f.exists():
            return 0.0
        try:
            return json.loads(f.read_text()).get("total_cost_usd", 0.0)
        except Exception:
            return 0.0

    def _ai_spend_pct(self, today: str) -> float:
        budget = float(os.environ.get("IMPERIO_DAILY_AI_BUDGET_USD", "0") or "0")
        if budget <= 0:
            return 0.0
        return self._ai_spend(today) / budget * 100

    def _clicks_today(self, today: str) -> int:
        click_log = IMPERIO_ROOT / "REVENUE" / "click_log.json"
        if not click_log.exists():
            return 0
        try:
            with open(click_log) as f:
                return sum(1 for line in f if today in line)
        except Exception:
            return 0

    def _campaign_count(self) -> int:
        f = IMPERIO_ROOT / "REVENUE" / "campaigns.json"
        if not f.exists():
            return 0
        try:
            data = json.loads(f.read_text())
            return len(data.get("campaigns", {}))
        except Exception:
            return 0

    def _top_campaigns(self, limit: int) -> list[dict]:
        f = IMPERIO_ROOT / "REVENUE" / "campaigns.json"
        if not f.exists():
            return []
        try:
            data = json.loads(f.read_text())
            campaigns = data.get("campaigns", {})
            ranked = []
            for asin, cdata in campaigns.items():
                ranked.append({
                    "asin": asin,
                    "name": cdata.get("product_name", asin)[:40],
                    "posts": cdata.get("posts_count", 0),
                    "phase": cdata.get("phase", "?"),
                })
            ranked.sort(key=lambda x: -x["posts"])
            return ranked[:limit]
        except Exception:
            return []

    def _circuit_breakers(self) -> dict[str, str]:
        f = IMPERIO_ROOT / "logs" / "guardrails" / "circuit_breaker_state.json"
        if not f.exists():
            return {}
        try:
            data = json.loads(f.read_text())
            return {name: s.get("state", "CLOSED") for name, s in data.items()}
        except Exception:
            return {}

    def _platform_health(self) -> dict[str, int]:
        """Compute health from posting_safety_layer at runtime."""
        try:
            import sys
            rev_dir = str(IMPERIO_ROOT / "REVENUE")
            if rev_dir not in sys.path:
                sys.path.insert(0, rev_dir)
            from posting_safety_layer import PostingSafetyLayer
            safety = PostingSafetyLayer()
            result = {}
            for plat in ["telegram", "instagram", "twitter", "pinterest", "tiktok"]:
                health = safety.compute_account_health(plat)
                result[plat] = health.get("score", 100)
            return result
        except Exception:
            # Fallback: count posts per platform from safety file
            f = IMPERIO_ROOT / "REVENUE" / "posting_safety.json"
            if not f.exists():
                return {}
            try:
                data = json.loads(f.read_text())
                posts = data.get("posts", [])
                platforms = set(p.get("platform", "") for p in posts)
                return {plat: 100 for plat in platforms if plat}
            except Exception:
                return {}

    def _recent_quality(self, limit: int) -> list[dict]:
        f = IMPERIO_ROOT / "logs" / "quality_gate.jsonl"
        if not f.exists():
            return []
        entries = []
        try:
            with open(f) as fh:
                for line in fh:
                    try:
                        entries.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        return entries[-limit:]

    def _engagement_count(self, today: str, metric: str) -> int:
        eng_dir = IMPERIO_ROOT / "engagement_engine"
        if not eng_dir.exists():
            return 0
        log_file = eng_dir / "response_log.jsonl"
        if not log_file.exists():
            return 0
        try:
            with open(log_file) as f:
                return sum(1 for line in f if today in line)
        except Exception:
            return 0

    def _trending(self, limit: int) -> list[str]:
        # daily_brief.json has the latest scouted products
        f = IMPERIO_ROOT / "REVENUE" / "daily_brief.json"
        if not f.exists():
            return []
        try:
            data = json.loads(f.read_text())
            products = data.get("products", [])
            return [p.get("name", p.get("title", "?"))[:50] for p in products[:limit]]
        except Exception:
            return []

    def _ssmie_mode(self) -> str:
        f = IMPERIO_ROOT / "REVENUE" / "ssmie_state.json"
        if not f.exists():
            return "unknown"
        try:
            data = json.loads(f.read_text())
            # Check for protective_mode collapse
            if data.get("system_state") == "protective_mode":
                return "PROTECTIVE"
            return data.get("system_health", data.get("growth_state", "unknown"))
        except Exception:
            return "unknown"

    def _ssmie_protective(self) -> bool:
        f = IMPERIO_ROOT / "REVENUE" / "ssmie_state.json"
        if not f.exists():
            return False
        try:
            data = json.loads(f.read_text())
            # Protective mode can be top-level (collapsed) or nested
            if data.get("system_state") == "protective_mode":
                return True
            return False
        except Exception:
            return False

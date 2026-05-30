"""
executive_truth_engine.py — Single source of truth for all IMPERIO metrics.

ONE object. ONE cache. Every Telegram command reads from here.
No schema guessing — built against actual files on disk (audited 2026-05-30).

Reads:
  - campaigns.json           {"campaigns": {ASIN: {..., posts_count, post_history}}}
  - click_log.json            {"clicks": [{event_type, timestamp, product_id, platform}]}
  - daily_brief.json          {"products": [{asin, name, final_score, category}]}
  - posting_safety.json       {"posts": [{timestamp, platform, product, category}]}
  - posts_log.jsonl           {ts, platform, product, status}
  - instagram_posts.jsonl     {timestamp, asin, product_name}
  - twitter_posts.jsonl       {ts, url, platform}
  - pinterest_posts.jsonl     {ts, platform}
  - tiktok_posts.jsonl        {ts, platform}  (may not exist yet)
  - ssmie_state.json          {system_health, growth_state, system_state, summary}
  - system_memory.json        {formula_priors, update_count}
  - tasks.db                  SQLite: tasks, execution_traces
  - logs/events/*.jsonl       {event_type, severity, timestamp, data}
  - logs/guardrails/circuit_breaker_state.json   (may not exist)
  - logs/guardrails/daily_spend_YYYY-MM-DD.json  (may not exist)

100% deterministic. No LLM calls. No imports from other executive_layer modules.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")


@dataclass
class CampaignMetrics:
    asin: str
    product_name: str
    category: str
    phase: str
    status: str
    posts_count: int
    clicks: int
    platforms_posted: list[str]
    performance_score: int
    created: str


@dataclass
class PlatformMetrics:
    name: str
    posts_today: int
    posts_week: int
    posts_total: int
    failures_today: int
    health_score: int  # 0-100


@dataclass
class ExecutiveState:
    """Complete system truth at a point in time."""
    timestamp: str

    # ── Posts ──
    posts_today: int
    posts_week: int
    posts_total: int
    posts_by_platform: dict[str, int]       # today
    posts_by_platform_week: dict[str, int]

    # ── Clicks ──
    clicks_today: int
    clicks_week: int
    clicks_total: int
    clicks_by_product: dict[str, int]       # all-time
    clicks_by_platform: dict[str, int]      # all-time

    # ── Revenue ──
    revenue_tracked: float  # from tasks.db revenue_log (may be 0)

    # ── Campaigns ──
    campaigns: list[CampaignMetrics]
    active_campaigns: int
    top_product: str        # most posts + clicks
    top_product_asin: str

    # ── Platforms ──
    platforms: list[PlatformMetrics]
    top_platform: str       # most posts today
    worst_platform: str     # fewest posts or most failures

    # ── Failures ──
    failures_today: int
    failures_week: int
    recent_errors: list[dict]  # [{event_type, error, timestamp, severity}]
    executor_failures: dict[str, int]  # {executor: count}

    # ── Health ──
    health_score: int       # 0-100 composite
    circuit_breakers: dict[str, str]  # {name: CLOSED|OPEN|HALF_OPEN}
    ssmie_mode: str
    ssmie_health: str
    pipeline_status: str

    # ── AI Spend ──
    ai_spend_today: float
    ai_budget: float
    ai_spend_pct: float

    # ── Scouting ──
    scouted_products: int
    top_scouted: list[dict]  # [{name, asin, score}]

    # ── Tasks ──
    tasks_today: int
    tasks_failed_today: int
    tasks_success_rate: float


class ExecutiveTruthEngine:
    """
    Single source of truth. Reads all data sources, normalizes into
    ExecutiveState. Caches for 60 seconds.
    """

    def __init__(self, cache_ttl: int = 60):
        self._cache: ExecutiveState | None = None
        self._cache_ts: float = 0
        self._cache_ttl = cache_ttl

    def state(self, force_refresh: bool = False) -> ExecutiveState:
        """Get current ExecutiveState. Cached for performance."""
        now = time.time()
        if not force_refresh and self._cache and (now - self._cache_ts) < self._cache_ttl:
            return self._cache

        state = self._build_state()
        self._cache = state
        self._cache_ts = now
        return state

    def invalidate(self):
        """Force next call to rebuild."""
        self._cache = None

    # ── Builder ───────────────────────────────────────────────

    def _build_state(self) -> ExecutiveState:
        today = time.strftime("%Y-%m-%d")
        week_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

        # Read all sources
        posts = self._read_all_posts()
        clicks = self._read_clicks()
        campaigns = self._read_campaigns()
        events = self._read_events(today, week_start)
        cb_state = self._read_json("logs/guardrails/circuit_breaker_state.json", {})
        spend_data = self._read_json(f"logs/guardrails/daily_spend_{today}.json", {})
        ssmie = self._read_json("REVENUE/ssmie_state.json", {})
        brief = self._read_json("REVENUE/daily_brief.json", {})
        tasks = self._read_tasks(today)

        # ── Posts aggregation ──
        posts_today = [p for p in posts if p.get("date", "")[:10] == today]
        posts_week = [p for p in posts if p.get("date", "")[:10] >= week_start]

        posts_by_platform_today = self._count_by_key(posts_today, "platform")
        posts_by_platform_week = self._count_by_key(posts_week, "platform")

        # ── Clicks aggregation ──
        all_clicks = clicks.get("clicks", [])
        clicks_today_list = [c for c in all_clicks if c.get("timestamp", "")[:10] == today]
        clicks_week_list = [c for c in all_clicks if c.get("timestamp", "")[:10] >= week_start]
        clicks_by_product = self._count_by_key(all_clicks, "product_id")
        clicks_by_platform = self._count_by_key(all_clicks, "platform")

        # ── Campaign metrics ──
        campaign_metrics = []
        for asin, cdata in campaigns.items():
            # Count clicks for this ASIN
            asin_clicks = sum(1 for c in all_clicks if c.get("product_id") == asin)
            # Platforms from post_history
            platforms_posted = list(set(
                p.get("platform", "") for p in cdata.get("post_history", [])
            ))
            campaign_metrics.append(CampaignMetrics(
                asin=asin,
                product_name=cdata.get("product_name", asin)[:60],
                category=cdata.get("category", "unknown"),
                phase=cdata.get("phase", "UNKNOWN"),
                status=cdata.get("status", "unknown"),
                posts_count=cdata.get("posts_count", 0),
                clicks=asin_clicks,
                platforms_posted=platforms_posted,
                performance_score=cdata.get("performance_score", 0),
                created=cdata.get("created", "")[:10],
            ))
        campaign_metrics.sort(key=lambda c: -(c.posts_count + c.clicks * 10))

        # Top product = most posts + weighted clicks
        top_product = campaign_metrics[0].product_name if campaign_metrics else "none"
        top_product_asin = campaign_metrics[0].asin if campaign_metrics else ""

        # ── Platform metrics ──
        all_platforms = ["telegram", "instagram", "twitter", "pinterest", "tiktok"]
        platform_metrics = []
        platform_health = self._compute_platform_health()
        for plat in all_platforms:
            p_today = posts_by_platform_today.get(plat, 0)
            p_week = posts_by_platform_week.get(plat, 0)
            p_total = sum(1 for p in posts if p.get("platform") == plat)
            p_failures = events["failures_by_executor"].get(plat, 0)
            health = platform_health.get(plat, 100)
            platform_metrics.append(PlatformMetrics(
                name=plat,
                posts_today=p_today,
                posts_week=p_week,
                posts_total=p_total,
                failures_today=p_failures,
                health_score=health,
            ))

        # Top/worst platform by posts today
        active_plats = [p for p in platform_metrics if p.posts_today > 0]
        if active_plats:
            top_plat = max(active_plats, key=lambda p: p.posts_today).name
        else:
            top_plat = max(platform_metrics, key=lambda p: p.posts_total).name if platform_metrics else "none"

        worst_plat = min(platform_metrics, key=lambda p: p.health_score).name if platform_metrics else "none"

        # ── Health score ──
        # Composite: 40% platform health avg, 30% success rate, 20% no open circuits, 10% SSMIE
        avg_health = sum(p.health_score for p in platform_metrics) / len(platform_metrics) if platform_metrics else 100
        total_attempts = len(posts_today) + events["failures_today"]
        success_rate = (len(posts_today) / total_attempts * 100) if total_attempts > 0 else 100
        open_circuits = sum(1 for v in cb_state.values() if isinstance(v, dict) and v.get("state") == "OPEN")
        circuit_penalty = max(0, 100 - open_circuits * 25)
        ssmie_score = 100 if ssmie.get("system_state") != "protective_mode" else 40

        health_score = int(
            avg_health * 0.4 +
            success_rate * 0.3 +
            circuit_penalty * 0.2 +
            ssmie_score * 0.1
        )

        # ── AI spend ──
        ai_spend = spend_data.get("total_cost_usd", 0.0)
        ai_budget = float(os.environ.get("IMPERIO_DAILY_AI_BUDGET_USD", "0") or "0")
        ai_spend_pct = (ai_spend / ai_budget * 100) if ai_budget > 0 else 0.0

        # ── Scouting ──
        scouted = brief.get("products", [])
        top_scouted = [
            {"name": p.get("name", "?")[:50], "asin": p.get("asin", ""), "score": p.get("final_score", 0)}
            for p in scouted[:5]
        ]

        # ── Pipeline status ──
        pipeline_status = self._pipeline_status()

        # ── Circuit breakers ──
        cb_parsed = {}
        for name, val in cb_state.items():
            if isinstance(val, dict):
                cb_parsed[name] = val.get("state", "CLOSED")

        # ── SSMIE ──
        ssmie_mode = ssmie.get("growth_state", "unknown")
        ssmie_health = ssmie.get("system_health", "unknown")
        if ssmie.get("system_state") == "protective_mode":
            ssmie_mode = "PROTECTIVE"
            ssmie_health = "protective"

        return ExecutiveState(
            timestamp=timestamp,
            posts_today=len(posts_today),
            posts_week=len(posts_week),
            posts_total=len(posts),
            posts_by_platform=posts_by_platform_today,
            posts_by_platform_week=posts_by_platform_week,
            clicks_today=len(clicks_today_list),
            clicks_week=len(clicks_week_list),
            clicks_total=len(all_clicks),
            clicks_by_product=clicks_by_product,
            clicks_by_platform=clicks_by_platform,
            revenue_tracked=tasks["revenue"],
            campaigns=campaign_metrics,
            active_campaigns=len([c for c in campaign_metrics if c.status == "active"]),
            top_product=top_product,
            top_product_asin=top_product_asin,
            platforms=platform_metrics,
            top_platform=top_plat,
            worst_platform=worst_plat,
            failures_today=events["failures_today"],
            failures_week=events["failures_week"],
            recent_errors=events["recent_errors"],
            executor_failures=events["failures_by_executor"],
            health_score=health_score,
            circuit_breakers=cb_parsed,
            ssmie_mode=ssmie_mode,
            ssmie_health=ssmie_health,
            pipeline_status=pipeline_status,
            ai_spend_today=ai_spend,
            ai_budget=ai_budget,
            ai_spend_pct=ai_spend_pct,
            scouted_products=len(scouted),
            top_scouted=top_scouted,
            tasks_today=tasks["total"],
            tasks_failed_today=tasks["failed"],
            tasks_success_rate=tasks["success_rate"],
        )

    # ── Data Readers ──────────────────────────────────────────

    def _read_all_posts(self) -> list[dict]:
        """Read all posting logs, normalize to {date, platform, product, status}."""
        posts = []

        # posts_log.jsonl — main log
        posts += self._read_jsonl("REVENUE/posts_log.jsonl", normalize=self._norm_posts_log)

        # Platform-specific logs (for posts not in main log)
        seen_keys = set()
        for p in posts:
            key = (p.get("date", "")[:10], p.get("platform", ""), p.get("product", "")[:20])
            seen_keys.add(key)

        for log_name, plat, norm_fn in [
            ("REVENUE/instagram_posts.jsonl", "instagram", self._norm_ig),
            ("REVENUE/twitter_posts.jsonl", "twitter", self._norm_twitter),
            ("REVENUE/pinterest_posts.jsonl", "pinterest", self._norm_pinterest),
            ("REVENUE/tiktok_posts.jsonl", "tiktok", self._norm_tiktok),
        ]:
            for entry in self._read_jsonl(log_name, normalize=norm_fn):
                key = (entry.get("date", "")[:10], entry.get("platform", ""), entry.get("product", "")[:20])
                if key not in seen_keys:
                    posts.append(entry)
                    seen_keys.add(key)

        return posts

    def _norm_posts_log(self, raw: dict) -> dict:
        ts = raw.get("ts", raw.get("timestamp", ""))
        return {
            "date": ts[:10] if ts else "",
            "platform": raw.get("platform", "unknown"),
            "product": raw.get("product", "")[:60],
            "status": raw.get("status", "success"),
        }

    def _norm_ig(self, raw: dict) -> dict:
        ts = raw.get("timestamp", "")
        return {
            "date": ts[:10] if ts else "",
            "platform": "instagram",
            "product": raw.get("product_name", "")[:60],
            "status": "success",
        }

    def _norm_twitter(self, raw: dict) -> dict:
        ts = raw.get("ts", "")
        return {
            "date": ts[:10] if ts else "",
            "platform": "twitter",
            "product": raw.get("text", "")[:60],
            "status": "success",
        }

    def _norm_pinterest(self, raw: dict) -> dict:
        ts = raw.get("ts", "")
        return {
            "date": ts[:10] if ts else "",
            "platform": "pinterest",
            "product": raw.get("title", "")[:60],
            "status": "success",
        }

    def _norm_tiktok(self, raw: dict) -> dict:
        ts = raw.get("ts", raw.get("timestamp", ""))
        return {
            "date": ts[:10] if ts else "",
            "platform": "tiktok",
            "product": raw.get("product", raw.get("title", ""))[:60] if raw.get("product") or raw.get("title") else "",
            "status": "success",
        }

    def _read_clicks(self) -> dict:
        """Read click_log.json — {"clicks": [...]}."""
        return self._read_json("REVENUE/click_log.json", {"clicks": []})

    def _read_campaigns(self) -> dict:
        """Read campaigns.json — nested under "campaigns" key."""
        raw = self._read_json("REVENUE/campaigns.json", {})
        return raw.get("campaigns", raw)

    def _read_events(self, today: str, week_start: str) -> dict:
        """Read event logs, count failures."""
        result = {
            "failures_today": 0,
            "failures_week": 0,
            "recent_errors": [],
            "failures_by_executor": {},
        }

        events_dir = IMPERIO_ROOT / "logs" / "events"
        if not events_dir.exists():
            return result

        all_errors = []
        for event_file in sorted(events_dir.glob("*.jsonl")):
            file_date = event_file.stem  # YYYY-MM-DD
            if file_date < week_start:
                continue
            try:
                with open(event_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        et = entry.get("event_type", "")
                        if "failed" not in et and "error" not in et.lower():
                            continue
                        ts = entry.get("timestamp", "")[:10]
                        if ts == today:
                            result["failures_today"] += 1
                        result["failures_week"] += 1

                        # Track by executor
                        executor = entry.get("data", {}).get("executor", "")
                        if executor:
                            result["failures_by_executor"][executor] = \
                                result["failures_by_executor"].get(executor, 0) + 1

                        all_errors.append({
                            "event_type": et,
                            "error": entry.get("data", {}).get("error", "")[:200],
                            "timestamp": entry.get("timestamp", ""),
                            "severity": entry.get("severity", "info"),
                        })
            except Exception:
                continue

        result["recent_errors"] = all_errors[-10:]
        return result

    def _read_tasks(self, today: str) -> dict:
        """Read tasks.db for today's task stats."""
        result = {"total": 0, "failed": 0, "success_rate": 100.0, "revenue": 0.0}
        db_path = IMPERIO_ROOT / "operator" / "tasks.db"
        if not db_path.exists():
            return result
        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute(
                "SELECT status, COUNT(*) FROM tasks WHERE created_at LIKE ? GROUP BY status",
                (f"{today}%",)
            )
            for status, count in cur.fetchall():
                result["total"] += count
                if status == "failed":
                    result["failed"] += count
            if result["total"] > 0:
                result["success_rate"] = (
                    (result["total"] - result["failed"]) / result["total"] * 100
                )
            # Revenue
            cur.execute("SELECT COALESCE(SUM(amount_usd), 0) FROM revenue_log")
            result["revenue"] = cur.fetchone()[0] or 0.0
            conn.close()
        except Exception:
            pass
        return result

    def _compute_platform_health(self) -> dict[str, int]:
        """Compute health via PostingSafetyLayer at runtime."""
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
            return {}

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

    # ── Generic Helpers ───────────────────────────────────────

    def _read_json(self, rel_path: str, default):
        fp = IMPERIO_ROOT / rel_path
        if not fp.exists():
            return default
        try:
            return json.loads(fp.read_text())
        except Exception:
            return default

    def _read_jsonl(self, rel_path: str, normalize=None) -> list[dict]:
        fp = IMPERIO_ROOT / rel_path
        if not fp.exists():
            return []
        entries = []
        try:
            with open(fp) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw = json.loads(line)
                        entries.append(normalize(raw) if normalize else raw)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        return entries

    def _count_by_key(self, items: list[dict], key: str) -> dict[str, int]:
        counts = {}
        for item in items:
            val = item.get(key, "unknown")
            if val:
                counts[val] = counts.get(val, 0) + 1
        return counts

    # ── Formatted Outputs ─────────────────────────────────────

    def format_status(self, s: ExecutiveState = None) -> str:
        """Quick status for /status command."""
        if s is None:
            s = self.state()
        lines = [
            f"Pipeline: {s.pipeline_status.upper()}",
            f"Posts hoy: {s.posts_today} | Semana: {s.posts_week}",
            f"Clicks hoy: {s.clicks_today} | Total: {s.clicks_total}",
            f"Fallos hoy: {s.failures_today}",
            f"Health: {s.health_score}/100",
            f"SSMIE: {s.ssmie_health} ({s.ssmie_mode})",
            f"Campañas activas: {s.active_campaigns}",
        ]
        if s.ai_spend_today > 0:
            lines.append(f"AI spend: ${s.ai_spend_today:.4f}")
        open_cb = [k for k, v in s.circuit_breakers.items() if v == "OPEN"]
        if open_cb:
            lines.append(f"⚠ Executors OPEN: {', '.join(open_cb)}")
        return "\n".join(lines)

    def format_executive(self, s: ExecutiveState = None) -> str:
        """Full executive summary for /executive command."""
        if s is None:
            s = self.state()

        lines = [
            "═══ IMPERIO EXECUTIVE SUMMARY ═══",
            f"  {s.timestamp}",
            f"  Health: {s.health_score}/100 | Pipeline: {s.pipeline_status.upper()}",
            f"  SSMIE: {s.ssmie_health} ({s.ssmie_mode})",
            "",
            "── Posts ──",
        ]
        for plat in s.platforms:
            if plat.posts_today > 0 or plat.posts_total > 0:
                lines.append(f"  {plat.name}: {plat.posts_today} hoy | {plat.posts_week} semana | {plat.posts_total} total")
        lines.append(f"  TOTAL: {s.posts_today} hoy | {s.posts_week} semana | {s.posts_total} total")

        lines.append(f"\n── Clicks ──")
        lines.append(f"  Hoy: {s.clicks_today} | Semana: {s.clicks_week} | Total: {s.clicks_total}")
        if s.clicks_by_product:
            lines.append("  Por producto:")
            for prod, count in sorted(s.clicks_by_product.items(), key=lambda x: -x[1])[:5]:
                lines.append(f"    {prod}: {count}")

        lines.append(f"\n── Campañas ({s.active_campaigns}) ──")
        for c in s.campaigns[:5]:
            lines.append(f"  {c.product_name}")
            lines.append(f"    Phase: {c.phase} | Posts: {c.posts_count} | Clicks: {c.clicks}")
            if c.platforms_posted:
                lines.append(f"    Plataformas: {', '.join(c.platforms_posted)}")

        if s.failures_today > 0 or s.failures_week > 0:
            lines.append(f"\n── Fallos ──")
            lines.append(f"  Hoy: {s.failures_today} | Semana: {s.failures_week}")
            for e in s.recent_errors[-3:]:
                lines.append(f"  • [{e['severity']}] {e['event_type']}: {e['error'][:80]}")

        lines.append(f"\n── Executors ──")
        for plat in s.platforms:
            bar = "█" * (plat.health_score // 10) + "░" * (10 - plat.health_score // 10)
            icon = "✅" if plat.health_score >= 80 else "⚠️" if plat.health_score >= 50 else "❌"
            lines.append(f"  {icon} {plat.name}: {bar} {plat.health_score}/100")
        if s.circuit_breakers:
            for name, state in s.circuit_breakers.items():
                icon = {"CLOSED": "✅", "OPEN": "❌", "HALF_OPEN": "⚠️"}.get(state, "?")
                lines.append(f"  CB {icon} {name}: {state}")

        if s.ai_spend_today > 0 or s.ai_budget > 0:
            lines.append(f"\n── AI Spend ──")
            lines.append(f"  ${s.ai_spend_today:.4f}" + (
                f" ({s.ai_spend_pct:.0f}% de ${s.ai_budget:.2f})" if s.ai_budget > 0 else ""))

        if s.top_scouted:
            lines.append(f"\n── Scouted ({s.scouted_products}) ──")
            for p in s.top_scouted[:3]:
                lines.append(f"  • {p['name']} (score: {p['score']})")

        lines.append(f"\n── Top Product ──")
        lines.append(f"  {s.top_product}")
        lines.append(f"\n  Best platform: {s.top_platform}")
        lines.append(f"  Worst platform: {s.worst_platform}")

        lines.append("\n═══════════════════════════════")
        return "\n".join(lines)

    def format_campaigns(self, s: ExecutiveState = None) -> str:
        """Campaign detail for /campaigns command."""
        if s is None:
            s = self.state()
        if not s.campaigns:
            return "Sin campañas activas."
        lines = [f"Campañas activas ({s.active_campaigns}):"]
        for c in s.campaigns:
            lines.append(f"\n  {c.product_name}")
            lines.append(f"    ASIN: {c.asin}")
            lines.append(f"    Phase: {c.phase} | Status: {c.status}")
            lines.append(f"    Posts: {c.posts_count} | Clicks: {c.clicks}")
            lines.append(f"    Score: {c.performance_score} | Desde: {c.created}")
            if c.platforms_posted:
                lines.append(f"    Plataformas: {', '.join(c.platforms_posted)}")
        return "\n".join(lines)

    def format_failures(self, s: ExecutiveState = None) -> str:
        """Failure detail for /failures command."""
        if s is None:
            s = self.state()
        if not s.recent_errors:
            return "Sin fallos recientes."
        lines = [f"Fallos — Hoy: {s.failures_today} | Semana: {s.failures_week}"]
        for e in s.recent_errors[-5:]:
            lines.append(f"\n  [{e['severity'].upper()}] {e['event_type']}")
            lines.append(f"    {e['timestamp']}")
            if e['error']:
                lines.append(f"    {e['error'][:150]}")
        if s.executor_failures:
            lines.append("\nPor executor:")
            for ex, count in sorted(s.executor_failures.items(), key=lambda x: -x[1]):
                lines.append(f"  {ex}: {count} fallos")
        return "\n".join(lines)

    def format_health(self, s: ExecutiveState = None) -> str:
        """Health detail for /health command."""
        if s is None:
            s = self.state()
        lines = [f"Health Score: {s.health_score}/100", ""]
        for plat in s.platforms:
            bar = "█" * (plat.health_score // 10) + "░" * (10 - plat.health_score // 10)
            lines.append(f"  {plat.name}: {bar} {plat.health_score}/100 ({plat.posts_today} posts hoy)")
        if s.circuit_breakers:
            lines.append("\nCircuit Breakers:")
            for name, state in s.circuit_breakers.items():
                icon = {"CLOSED": "✅", "OPEN": "❌", "HALF_OPEN": "⚠️"}.get(state, "?")
                lines.append(f"  {icon} {name}: {state}")
        else:
            lines.append("\nCircuit Breakers: sin datos (archivo no existe)")
        return "\n".join(lines)

    def format_spend(self, s: ExecutiveState = None) -> str:
        """AI spend for /spend command."""
        if s is None:
            s = self.state()
        msg = f"AI spend hoy: ${s.ai_spend_today:.4f}"
        if s.ai_budget > 0:
            msg += f" ({s.ai_spend_pct:.0f}% de ${s.ai_budget:.2f})"
        else:
            msg += " (sin budget configurado)"
        return msg

    def format_clicks(self, s: ExecutiveState = None) -> str:
        """Click tracking for /clicks command."""
        if s is None:
            s = self.state()
        lines = [
            f"Clicks hoy: {s.clicks_today} | Semana: {s.clicks_week} | Total: {s.clicks_total}",
            f"Campañas activas: {s.active_campaigns}",
        ]
        if s.clicks_by_product:
            lines.append("\nPor producto:")
            for prod, count in sorted(s.clicks_by_product.items(), key=lambda x: -x[1])[:5]:
                lines.append(f"  {prod}: {count} clicks")
        if s.clicks_by_platform:
            lines.append("\nPor plataforma origen:")
            for plat, count in sorted(s.clicks_by_platform.items(), key=lambda x: -x[1]):
                lines.append(f"  {plat}: {count}")
        return "\n".join(lines)

    def answer_question(self, question: str, s: ExecutiveState = None) -> str | None:
        """
        Try to answer common questions deterministically.
        Returns None if can't answer — caller should use LLM.
        """
        if s is None:
            s = self.state()
        q = question.lower()

        # Product with most clicks
        if any(w in q for w in ["más clics", "más clicks", "most clicks", "mejor producto"]):
            if s.clicks_by_product:
                top = max(s.clicks_by_product.items(), key=lambda x: x[1])
                # Find product name from campaigns
                name = top[0]
                for c in s.campaigns:
                    if c.asin == top[0]:
                        name = c.product_name
                        break
                return f"Producto con más clics: {name} ({top[0]}) — {top[1]} clicks"
            return "Sin datos de clicks registrados todavía."

        # Platform with most engagement
        if any(w in q for w in ["más engagement", "mejor plataforma", "most engagement", "best platform"]):
            if s.platforms:
                best = max(s.platforms, key=lambda p: p.posts_total)
                return f"Plataforma con más actividad: {best.name} — {best.posts_total} posts total, {best.posts_today} hoy"
            return "Sin datos de plataformas."

        # What failed this week
        if any(w in q for w in ["falló esta semana", "failed this week", "qué falló", "errores semana"]):
            if s.failures_week == 0:
                return "Sin fallos esta semana."
            return self.format_failures(s)

        # Best campaign
        if any(w in q for w in ["mejor campaña", "best campaign", "campaña funciona"]):
            if s.campaigns:
                best = s.campaigns[0]  # Already sorted by posts+clicks
                return (
                    f"Mejor campaña: {best.product_name}\n"
                    f"  ASIN: {best.asin}\n"
                    f"  Phase: {best.phase} | Posts: {best.posts_count} | Clicks: {best.clicks}\n"
                    f"  Score: {best.performance_score} | Plataformas: {', '.join(best.platforms_posted)}"
                )
            return "Sin campañas activas."

        # Corrective action
        if any(w in q for w in ["acción correctiva", "recomiendas", "qué hacer", "corrective action"]):
            actions = []
            if s.health_score < 60:
                actions.append("Health bajo — revisar plataformas con score < 60")
            for plat in s.platforms:
                if plat.health_score < 60:
                    actions.append(f"Pausar {plat.name} (health {plat.health_score}/100)")
            for name, state in s.circuit_breakers.items():
                if state == "OPEN":
                    actions.append(f"Investigar executor {name} — circuit breaker OPEN")
            if s.ssmie_mode == "PROTECTIVE":
                actions.append("SSMIE en modo protectivo — reducir frecuencia")
            if s.failures_today >= 3:
                actions.append(f"{s.failures_today} fallos hoy — revisar logs")
            if not actions:
                actions.append("Sistema saludable. Continuar operación normal.")
            return "Acciones recomendadas:\n" + "\n".join(f"  → {a}" for a in actions)

        return None

#!/usr/bin/env python3
"""
autonomous_loop.py — HERMES 24/7 autonomous background agent.

Runs continuously. Cycles through tasks:
1. System monitoring (every 5 min)
2. Product scouting (every 2h)
3. Performance analysis (every 1h)
4. Self-improvement (every 4h)
5. Telegram alerts (on anomaly)

Uses ONLY free APIs:
- OpenRouter free models (Llama 3.1 8B, Gemma, Qwen)
- Ollama local (Qwen 2.5 7B)

HERMES NEVER:
- deletes files
- pushes git
- modifies secrets
- executes shell commands
- modifies deterministic core
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
sys.path.insert(0, str(IMPERIO_ROOT))

from core.supervisor.supervisor_loop import HermesSupervisor
from executive_layer.planning_engine import PlanningEngine
from executive_layer.llm_reasoning import reason
from executive_layer.daily_executive_report import DailyExecutiveReport

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("hermes.autonomous")

# Cycle intervals (seconds)
MONITOR_INTERVAL = 300       # 5 min
SCOUT_INTERVAL = 7200        # 2h
PERFORMANCE_INTERVAL = 3600  # 1h
SELF_IMPROVE_INTERVAL = 14400  # 4h
CREATIVE_INTERVAL = 10800     # 3h
META_COGNITIVE_INTERVAL = 14400  # 4h
CREATIVE_DIGEST_INTERVAL = 86400  # 24h (9am daily)
WEEKLY_DIGEST_INTERVAL = 604800  # 7 days (Monday 9am)
DAILY_REPORT_INTERVAL = 86400  # 24h


class AutonomousLoop:
    """
    Background agent that continuously monitors, scouts, and improves.
    All operations are READ-ONLY or ADDITIVE-ONLY (writes to logs/state files).
    """

    def __init__(self):
        self._supervisor = HermesSupervisor()
        self._planner = PlanningEngine()
        self._running = False
        self._telegram_bot = None  # set via connect_telegram()
        self._daily_report = DailyExecutiveReport()

        # Last run timestamps
        self._last_monitor = 0
        self._last_scout = 0
        self._last_performance = 0
        self._last_improve = 0
        self._last_creative = 0
        self._last_meta_cognitive = 0
        self._last_creative_digest = 0
        self._last_weekly_digest = 0
        self._last_daily_report = 0

        # State
        self._consecutive_healthy = 0
        self._alert_cooldown: dict[str, float] = {}

    def connect_telegram(self, bot):
        """Connect Telegram bot for alerts."""
        self._telegram_bot = bot

    async def start(self):
        """Start autonomous loop."""
        self._running = True
        log.info("HERMES autonomous loop starting...")

        while self._running:
            now = time.time()

            try:
                # Monitor — every 5 min
                if now - self._last_monitor >= MONITOR_INTERVAL:
                    await self._cycle_monitor()
                    self._last_monitor = now

                # Performance analysis — every 1h
                if now - self._last_performance >= PERFORMANCE_INTERVAL:
                    await self._cycle_performance()
                    self._last_performance = now

                # Product scouting — every 2h
                if now - self._last_scout >= SCOUT_INTERVAL:
                    await self._cycle_scout()
                    self._last_scout = now

                # Self-improvement — every 4h
                if now - self._last_improve >= SELF_IMPROVE_INTERVAL:
                    await self._cycle_self_improve()
                    self._last_improve = now

                # Creative intelligence — every 3h
                if now - self._last_creative >= CREATIVE_INTERVAL:
                    await self._cycle_creative()
                    self._last_creative = now

                # Meta-cognitive orchestration — every 4h
                if now - self._last_meta_cognitive >= META_COGNITIVE_INTERVAL:
                    await self._cycle_meta_cognitive()
                    self._last_meta_cognitive = now

                # Weekly creative summary — Monday at ~9am
                if hour >= 9 and now - self._last_weekly_digest >= WEEKLY_DIGEST_INTERVAL:
                    await self._cycle_weekly_digest()
                    self._last_weekly_digest = now

                # Daily creative digest — once per day at ~9am
                if hour >= 9 and now - self._last_creative_digest >= CREATIVE_DIGEST_INTERVAL:
                    await self._cycle_creative_digest()
                    self._last_creative_digest = now

                # Daily executive report — once per day at ~8am
                if hour >= 8 and now - self._last_daily_report >= DAILY_REPORT_INTERVAL:
                    await self._cycle_daily_report()
                    self._last_daily_report = now

            except Exception as e:
                log.error(f"Autonomous cycle error: {e}")

            await asyncio.sleep(30)  # main loop tick

    async def stop(self):
        self._running = False

    # ── CYCLE: Monitor ─────────────────────────────────────────

    async def _cycle_monitor(self):
        """Check system health, detect anomalies, alert if needed."""
        log.debug("Monitor cycle...")
        report = self._supervisor.observe()

        # Track consecutive healthy checks
        if not report.anomalies:
            self._consecutive_healthy += 1
        else:
            self._consecutive_healthy = 0

            # Alert on new anomalies
            for anomaly in report.anomalies:
                await self._maybe_alert(
                    key=anomaly.anomaly_id,
                    severity=anomaly.severity.value,
                    title=anomaly.title,
                    body=anomaly.details,
                )

        # Log monitor state
        self._append_log("monitor", {
            "anomalies": len(report.anomalies),
            "pipeline": report.pipeline_status,
            "posts": report.posts_today,
            "failures": report.failures_today,
            "consecutive_healthy": self._consecutive_healthy,
        })

    # ── CYCLE: Daily Executive Report ─────────────────────────

    async def _cycle_daily_report(self):
        """Generate and send daily executive report to Telegram."""
        log.info("Daily executive report cycle...")
        try:
            report = await self._daily_report.generate()
            if self._telegram_bot:
                # Split long reports into chunks (Telegram 4096 char limit)
                for i in range(0, len(report), 4000):
                    await self._telegram_bot.send_message(report[i:i+4000])
            self._append_log("daily_report", {"sent": True, "length": len(report)})
        except Exception as e:
            log.error(f"Daily report failed: {e}")
            self._append_log("daily_report", {"sent": False, "error": str(e)[:200]})

    # ── CYCLE: Performance Analysis ────────────────────────────

    async def _cycle_performance(self):
        """Analyze performance trends, generate insights."""
        log.info("Performance analysis cycle...")

        report = self._supervisor.observe()
        total = report.posts_today + report.failures_today
        success_rate = (report.posts_today / total * 100) if total > 0 else 0

        # Read campaign data
        campaigns = self._read_campaigns()
        active_count = len(campaigns)
        top_campaigns = self._rank_campaigns(campaigns)

        # Use LLM for insight generation
        context = (
            f"Posts hoy: {report.posts_today}\n"
            f"Fallos: {report.failures_today}\n"
            f"Success rate: {success_rate:.0f}%\n"
            f"AI spend: ${report.ai_spend_today:.4f}\n"
            f"Campañas activas: {active_count}\n"
        )
        if top_campaigns:
            context += "Top campañas:\n"
            for name, posts in top_campaigns[:3]:
                context += f"  - {name}: {posts} posts\n"

        try:
            insight = await reason(
                f"Analiza este rendimiento de un sistema de affiliate marketing y da 2-3 insights accionables:\n\n{context}",
                system_prompt="Eres un analista de performance de marketing de afiliados. Responde en español, máximo 3 líneas.",
                max_tokens=200,
            )
            self._append_log("performance_insight", {
                "success_rate": success_rate,
                "posts": report.posts_today,
                "insight": insight[:500],
            })
        except Exception as e:
            log.debug(f"Performance LLM failed: {e}")

    # ── CYCLE: Product Scouting ────────────────────────────────

    async def _cycle_scout(self):
        """Scout for trending products using free APIs."""
        log.info("Product scouting cycle...")

        # Read existing campaigns to avoid duplicates
        campaigns = self._read_campaigns()
        existing_asins = set(campaigns.keys())

        # Read trend data from daily_brief
        trend_file = IMPERIO_ROOT / "REVENUE" / "daily_brief.json"
        if trend_file.exists():
            try:
                brief = json.loads(trend_file.read_text())
                trends = brief.get("products", [])
                # Analyze with LLM
                product_list = []
                for p in trends[:10]:
                    name = p.get("name", p.get("title", ""))[:50]
                    asin = p.get("asin", "")
                    if asin not in existing_asins:
                        product_list.append(f"- {name} (ASIN: {asin})")

                if product_list:
                    prompt = (
                        "De estos productos trending de Amazon, cuáles 3 tienen más potencial viral "
                        "para contenido de afiliado en Instagram/TikTok? Explica por qué en 1 línea cada uno:\n\n"
                        + "\n".join(product_list[:10])
                    )
                    recommendation = await reason(
                        prompt,
                        system_prompt="Eres un experto en marketing de afiliados de Amazon. Responde en español.",
                        max_tokens=250,
                    )
                    self._append_log("scout_recommendation", {
                        "products_analyzed": len(product_list),
                        "recommendation": recommendation[:500],
                    })
            except Exception as e:
                log.debug(f"Scout analysis failed: {e}")

    # ── CYCLE: Self-Improvement ────────────────────────────────

    async def _cycle_self_improve(self):
        """Analyze own performance and suggest improvements."""
        log.info("Self-improvement cycle...")

        # Read recent logs
        monitor_logs = self._read_recent_logs("monitor", limit=50)
        performance_logs = self._read_recent_logs("performance_insight", limit=10)

        # Calculate trends
        anomaly_counts = [l.get("anomalies", 0) for l in monitor_logs]
        avg_anomalies = sum(anomaly_counts) / len(anomaly_counts) if anomaly_counts else 0

        healthy_streaks = [l.get("consecutive_healthy", 0) for l in monitor_logs]
        max_healthy = max(healthy_streaks) if healthy_streaks else 0

        context = (
            f"Últimas {len(monitor_logs)} observaciones:\n"
            f"  Anomalías promedio: {avg_anomalies:.1f}\n"
            f"  Mayor racha saludable: {max_healthy} checks\n"
            f"  Insights generados: {len(performance_logs)}\n"
        )

        try:
            improvement = await reason(
                f"Eres HERMES, un supervisor autónomo de un sistema de marketing. "
                f"Analiza tu rendimiento reciente y sugiere 2 mejoras concretas:\n\n{context}",
                max_tokens=200,
            )
            self._append_log("self_improvement", {
                "avg_anomalies": avg_anomalies,
                "max_healthy_streak": max_healthy,
                "suggestion": improvement[:500],
            })
        except Exception as e:
            log.debug(f"Self-improve LLM failed: {e}")

    # ── CYCLE: Creative Intelligence ─────────────────────────

    async def _cycle_creative(self):
        """
        Run creative intelligence cycle: detect style fatigue,
        generate creative ideas, log output.

        Read-only advisory. Never mutates production pipeline.
        Feature flag: FEATURE_CREATIVE_CYCLE (default: enabled).
        """
        if os.environ.get("FEATURE_CREATIVE_CYCLE", "1") != "1":
            return

        log.info("Creative intelligence cycle...")
        try:
            from core.creative_intelligence.creative_loop_cycle import run_creative_cycle
            output = run_creative_cycle(persist=True)

            self._append_log("creative_cycle", {
                "ideas": output.ideas,
                "warnings": output.warnings,
                "opportunity": output.opportunity,
                "risk": output.risk,
                "global_fatigue": output.snapshot.global_style_fatigue,
                "campaigns_with_repetition": output.snapshot.campaigns_with_repetition,
            })

            # Proactive Telegram notification (feature-flagged, rate-limited)
            if (
                os.environ.get("FEATURE_PROACTIVE_TELEGRAM", "0") == "1"
                and self._telegram_bot
            ):
                # Only send if there's something notable
                fatigue = output.snapshot.global_style_fatigue
                if fatigue > 0.3 or output.snapshot.campaigns_underperforming > 0:
                    msg = output.format_for_telegram()
                    try:
                        await self._telegram_bot.send_message(msg)
                    except Exception as e:
                        log.error(f"Proactive Telegram failed: {e}")

        except Exception as e:
            log.error(f"Creative cycle failed: {e}")
            self._append_log("creative_cycle", {"error": str(e)[:200]})

    # ── CYCLE: Daily Creative Digest ───────────────────────

    async def _cycle_creative_digest(self):
        """
        Daily creative digest sent at 9am via Telegram.

        Guaranteed send — always posts the full meta-cognitive summary,
        regardless of risk level or fatigue thresholds.
        Separate from the 4h proactive alerts (which are conditional).

        Feature flag: FEATURE_META_COGNITIVE (same as orchestrator).
        Additionally gated by: FEATURE_CREATIVE_DIGEST (default: enabled).
        """
        if os.environ.get("FEATURE_META_COGNITIVE", "0") != "1":
            return
        if os.environ.get("FEATURE_CREATIVE_DIGEST", "1") != "1":
            return

        log.info("Daily creative digest cycle...")
        try:
            from core.meta_cognitive.orchestrator import HermesMetaOrchestrator
            orchestrator = HermesMetaOrchestrator()
            output = orchestrator.run_cycle(persist=True)

            # Always send — no conditional gate
            if self._telegram_bot:
                msg = output.format_for_telegram()
                # Prepend daily header
                date_str = time.strftime("%A %d %B %Y")
                header = f"☀️ *Daily Creative Digest* — {date_str}\n\n"
                full_msg = header + msg

                try:
                    # Split if needed (Telegram 4096 char limit)
                    for i in range(0, len(full_msg), 4000):
                        await self._telegram_bot.send_message(full_msg[i:i+4000])
                    self._append_log("creative_digest", {
                        "sent": True,
                        "length": len(full_msg),
                        "risk": output.state.risk.overall_risk_level,
                        "fatigue": output.state.creative.global_style_fatigue,
                    })
                except Exception as e:
                    log.error(f"Creative digest Telegram send failed: {e}")
                    self._append_log("creative_digest", {"sent": False, "error": str(e)[:200]})
            else:
                log.warning("Creative digest: no Telegram bot connected")
                self._append_log("creative_digest", {"sent": False, "error": "no bot"})

        except ImportError as e:
            log.error(f"Creative digest: meta-cognitive module unavailable: {e}")
            self._append_log("creative_digest", {"error": f"import: {e}"})
        except Exception as e:
            log.error(f"Creative digest failed: {e}")
            self._append_log("creative_digest", {"error": str(e)[:200]})

    # ── CYCLE: Weekly Creative Summary ───────────────────

    async def _cycle_weekly_digest(self):
        """
        Weekly creative summary sent Monday at 9am via Telegram.

        Aggregates last 7 days of meta_cognitive_log.json and shows trend lines
        for fatigue, risk, ideas, warnings, opportunities, and experiments.

        Uses shared HermesMetaOrchestrator.build_weekly_summary() — single source
        of truth for weekly aggregation logic.

        Feature flag: FEATURE_META_COGNITIVE (same as orchestrator).
        Additionally gated by: FEATURE_WEEKLY_DIGEST (default: enabled).
        Only sends on Monday.
        """
        # Only send on Monday (0 = Monday, 6 = Sunday)
        if time.localtime().tm_wday != 0:
            return

        if os.environ.get("FEATURE_META_COGNITIVE", "0") != "1":
            return
        if os.environ.get("FEATURE_WEEKLY_DIGEST", "1") != "1":
            return

        log.info("Weekly creative summary cycle...")
        try:
            from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

            log_file = IMPERIO_ROOT / "REVENUE" / "meta_cognitive_log.json"
            if not log_file.exists():
                self._append_log("weekly_digest", {"sent": False, "error": "no log file"})
                return

            data = json.loads(log_file.read_text())
            if not isinstance(data, list) or not data:
                self._append_log("weekly_digest", {"sent": False, "error": "empty log"})
                return

            # Filter to last 7 days
            cutoff = time.time() - 604800
            week_cycles = [
                d for d in data
                if isinstance(d, dict) and self._entry_timestamp(d) >= cutoff
            ]

            if not week_cycles:
                self._append_log("weekly_digest", {"sent": False, "error": "no recent cycles"})
                return

            # Build trend summary via shared orchestrator logic
            summary = HermesMetaOrchestrator.build_weekly_summary(week_cycles)

            # Send
            if self._telegram_bot:
                date_str = time.strftime("%d %B %Y")
                header = f"📊 *Weekly Creative Summary* — {date_str}\n\n"
                full_msg = header + summary

                try:
                    for i in range(0, len(full_msg), 4000):
                        await self._telegram_bot.send_message(full_msg[i:i+4000])
                    self._append_log("weekly_digest", {
                        "sent": True,
                        "cycles": len(week_cycles),
                        "length": len(full_msg),
                    })
                except Exception as e:
                    log.error(f"Weekly digest Telegram send failed: {e}")
                    self._append_log("weekly_digest", {"sent": False, "error": str(e)[:200]})
            else:
                log.warning("Weekly digest: no Telegram bot connected")
                self._append_log("weekly_digest", {"sent": False, "error": "no bot"})

        except ImportError as e:
            log.error(f"Weekly digest: import error: {e}")
            self._append_log("weekly_digest", {"error": f"import: {e}"})
        except Exception as e:
            log.error(f"Weekly digest failed: {e}")
            self._append_log("weekly_digest", {"error": str(e)[:200]})

    def _entry_timestamp(self, entry: dict) -> float:
        """Convert a log entry to epoch timestamp."""
        ts_str = entry.get("timestamp", entry.get("generated_at", ""))
        try:
            return time.mktime(time.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S"))
        except Exception:
            return 0

    # ── CYCLE: Meta-Cognitive Orchestration ──────────────────

    async def _cycle_meta_cognitive(self):
        """
        Run meta-cognitive orchestration cycle: unified system snapshot,
        cognitive synthesis, decision generation, proactive output.

        Read-only advisory. Never mutates production pipeline.
        Feature flag: FEATURE_META_COGNITIVE (default: disabled).
        """
        if os.environ.get("FEATURE_META_COGNITIVE", "0") != "1":
            return

        log.info("Meta-cognitive orchestration cycle...")
        try:
            from core.meta_cognitive.orchestrator import HermesMetaOrchestrator
            orchestrator = HermesMetaOrchestrator()
            output = orchestrator.run_cycle(persist=True)

            self._append_log("meta_cognitive", {
                "cycle_id": output.state.cycle_id,
                "duration_ms": output.cycle_duration_ms,
                "global_fatigue": output.state.creative.global_style_fatigue,
                "risk_level": output.state.risk.overall_risk_level,
                "health_score": output.state.performance.health_score,
                "ideas": output.state.ideas,
                "warnings": output.state.warnings,
                "opportunity": output.state.strategic_opportunity,
                "experiment": output.state.recommended_experiment,
            })

            # Proactive Telegram notification (feature-flagged, rate-limited)
            if (
                os.environ.get("FEATURE_PROACTIVE_TELEGRAM", "0") == "1"
                and self._telegram_bot
            ):
                # Send if risk is MEDIUM+ or fatigue > 0.3
                risk = output.state.risk.overall_risk_level
                fatigue = output.state.creative.global_style_fatigue
                if risk in ("HIGH", "CRITICAL", "MEDIUM") or fatigue > 0.3:
                    msg = output.format_for_telegram()
                    try:
                        await self._telegram_bot.send_message(msg)
                        self._append_log("meta_cognitive_telegram", {"sent": True})
                    except Exception as e:
                        log.error(f"Meta-cognitive Telegram failed: {e}")

        except ImportError as e:
            log.error(f"Meta-cognitive module unavailable: {e}")
            self._append_log("meta_cognitive", {"error": f"import: {e}"})
        except Exception as e:
            log.error(f"Meta-cognitive cycle failed: {e}")
            self._append_log("meta_cognitive", {"error": str(e)[:200]})

    # ── Helpers ────────────────────────────────────────────────

    async def _maybe_alert(self, key: str, severity: str, title: str, body: str):
        """Send Telegram alert with cooldown."""
        now = time.time()
        last = self._alert_cooldown.get(key, 0)
        if now - last < 600:  # 10 min cooldown per alert key
            return

        self._alert_cooldown[key] = now

        if self._telegram_bot:
            try:
                await self._telegram_bot.send_alert(title, body, severity)
            except Exception as e:
                log.error(f"Alert send failed: {e}")

    def _read_campaigns(self) -> dict:
        f = IMPERIO_ROOT / "REVENUE" / "campaigns.json"
        if not f.exists():
            return {}
        try:
            raw = json.loads(f.read_text())
            return raw.get("campaigns", raw)
        except Exception:
            return {}

    def _rank_campaigns(self, campaigns: dict) -> list[tuple[str, int]]:
        ranked = []
        for asin, data in campaigns.items():
            name = data.get("product_name", asin)[:40]
            posts = data.get("posts_count", data.get("total_posts", 0))
            ranked.append((name, posts))
        ranked.sort(key=lambda x: -x[1])
        return ranked

    def _read_recent_logs(self, log_type: str, limit: int = 20) -> list[dict]:
        log_file = IMPERIO_ROOT / "logs" / "hermes_autonomous.jsonl"
        if not log_file.exists():
            return []
        entries = []
        try:
            with open(log_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("type") == log_type:
                            entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        return entries[-limit:]

    def _append_log(self, log_type: str, data: dict):
        log_file = IMPERIO_ROOT / "logs" / "hermes_autonomous.jsonl"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "type": log_type,
            **data,
        }
        try:
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass


async def main():
    """Standalone entry point."""
    loop = AutonomousLoop()
    await loop.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Autonomous loop stopped.")

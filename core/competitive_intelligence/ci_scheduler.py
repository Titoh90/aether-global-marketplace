#!/usr/bin/env python3
"""
ci_scheduler.py — Background scheduler for Competitive Intelligence pipeline.

Runs the full CI pipeline on a schedule:
    1. Load competitors from registry
    2. Fingerprint public posts (patterns only)
    3. Build insights per account
    4. Rank trends
    5. Generate report
    6. Feed insights to Visual Intelligence (archetype_memory)
    7. Log results + persist report

Designed to be:
- Called from cron: python3 ci_scheduler.py --run
- Run as background loop: python3 ci_scheduler.py --loop (sleeps 24h)
- Tested with --dry-run

Rules:
- NEVER modifies the core pipeline, revenue system, or dispatch gate
- Non-blocking — individual account failures logged, never raised
- All external calls through dispatch()

Usage:
    python3 -m core.competitive_intelligence.ci_scheduler --run
    python3 -m core.competitive_intelligence.ci_scheduler --loop
    python3 -m core.competitive_intelligence.ci_scheduler --dry-run
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import time
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))


# ── Configuration ─────────────────────────────────────────────────────────────

_DEFAULT_INTERVAL_SECONDS = 86400  # 24 hours
_LOG_DIR = _IMPERIO_ROOT / "logs" / "competitive_intelligence"
_REPORT_DIR = _IMPERIO_ROOT / "memory" / "competitive_intelligence"

_log_dir_created = False
_report_dir_created = False


def _ensure_dirs() -> None:
    global _log_dir_created, _report_dir_created
    if not _log_dir_created:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        _log_dir_created = True
    if not _report_dir_created:
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        _report_dir_created = True


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _today_str() -> str:
    return datetime.date.today().isoformat()


def _log(msg: str) -> None:
    _ensure_dirs()
    ts = _now_iso()
    line = f"[{ts}] {msg}"
    print(line, file=sys.stderr)
    try:
        log_path = _LOG_DIR / f"ci_scheduler_{_today_str()}.log"
        with open(log_path, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass  # can't log to file, at least we printed


# CI_TEST_MODE env var for tests
_CI_TEST_MODE = os.environ.get("CI_TEST_MODE", "") == "1"


# ── Pipeline Runner ───────────────────────────────────────────────────────────

def run_ci_pipeline(
    vi_category: str = "competitive_intelligence",
    max_posts: int = 20,
) -> dict:
    """
    Execute the full CI pipeline once.

    Steps:
        1. Load active competitors from registry
        2. Fingerprint public posts
        3. Build insights
        4. Rank trends
        5. Generate report
        6. Feed insights to VI archetype_memory
        7. Persist report to disk
        8. Log summary

    Returns:
        Summary dict with counts and status.
        Never raises.
    """
    from core.competitive_intelligence.competitor_registry import get_active_competitors
    from core.competitive_intelligence.public_scraper import fingerprint_account
    from core.competitive_intelligence.insight_engine import build_insights
    from core.competitive_intelligence.trend_ranker import rank_trends
    from core.competitive_intelligence.report_generator import generate_report

    _log("CI Pipeline started")

    summary = {
        "run_at":        _now_iso(),
        "status":        "ok",
        "competitors":   0,
        "fingerprints":  0,
        "insights":      0,
        "trends":        0,
        "vi_fed":        0,
        "errors":        0,
        "error_details": [],
    }

    # ── Step 1: Load competitors ──────────────────────────────────────────────
    try:
        competitors = get_active_competitors()
    except Exception as e:
        _log(f"  ERROR loading competitors: {e}")
        summary["status"] = "error"
        summary["errors"] += 1
        summary["error_details"].append(f"registry: {e}")
        return summary

    if not competitors:
        _log("  No active competitors in registry — nothing to do")
        return summary

    summary["competitors"] = len(competitors)
    _log(f"  Loaded {len(competitors)} active competitor(s)")

    # ── Step 2: Fingerprint + Step 3: Build insights ─────────────────────────
    all_insights = []
    total_fingerprints = 0

    for acc in competitors:
        try:
            fps = fingerprint_account(acc, max_posts=max_posts)
            total_fingerprints += len(fps)

            # Estimate posts_per_week from account metadata (simplified)
            posts_per_week = 3.0  # conservative default
            if hasattr(acc, 'niche') and acc.niche:
                posts_per_week = 5.0 if acc.niche in ("tech", "luxury") else posts_per_week

            if fps:
                insight = build_insights(acc, fps, posts_per_week_est=posts_per_week)
                all_insights.append(insight)
        except Exception as e:
            _log(f"  WARNING: failed fingerprint/insight for {acc.username}: {e}")
            summary["errors"] += 1
            summary["error_details"].append(f"{acc.username}: {e}")

    summary["fingerprints"] = total_fingerprints
    summary["insights"] = len(all_insights)
    _log(f"  Fingerprints: {total_fingerprints} | Insights: {len(all_insights)}")

    if not all_insights:
        _log("  No insights generated — pipeline complete (no data)")
        return summary

    # ── Step 4: Rank trends ───────────────────────────────────────────────────
    try:
        trends = rank_trends(all_insights)
        summary["trends"] = len(trends)
        _log(f"  Trends ranked: {len(trends)}")
    except Exception as e:
        _log(f"  ERROR ranking trends: {e}")
        summary["errors"] += 1
        summary["error_details"].append(f"rank_trends: {e}")
        trends = []

    # ── Step 5: Generate report ───────────────────────────────────────────────
    try:
        report = generate_report(trends, all_insights)
        _ensure_dirs()
        report_path = _REPORT_DIR / f"ci_report_{_today_str()}.json"
        report_path.write_text(json.dumps(report.to_dict(), indent=2, default=str))
        _log(f"  Report saved: {report_path}")
    except Exception as e:
        _log(f"  ERROR generating report: {e}")
        summary["errors"] += 1
        summary["error_details"].append(f"report: {e}")
        report = None

    # ── Step 6: Feed insights to Visual Intelligence ──────────────────────────
    try:
        from core.competitive_intelligence.ci_to_vi_bridge import feed_insights_to_vi
        vi_result = feed_insights_to_vi(all_insights, category=vi_category)
        summary["vi_fed"] = vi_result["fed"]
        _log(f"  VI feed: {vi_result['fed']} fed, {vi_result['skipped']} skipped, {vi_result['errors']} errors")
    except Exception as e:
        _log(f"  ERROR feeding VI: {e}")
        summary["errors"] += 1
        summary["error_details"].append(f"vi_bridge: {e}")

    # ── Step 7: Persist summary ───────────────────────────────────────────────
    try:
        _ensure_dirs()
        summary_path = _REPORT_DIR / f"ci_summary_{_today_str()}.json"
        summary_path.write_text(json.dumps(summary, indent=2, default=str))
    except Exception as e:
        _log(f"  WARNING: couldn't persist summary: {e}")

    _log(f"  CI Pipeline complete — {summary['competitors']} accounts, {summary['insights']} insights, {summary['vi_fed']} fed to VI")
    return summary


# ── Background Loop ───────────────────────────────────────────────────────────

def run_background_loop(
    interval_seconds: float = _DEFAULT_INTERVAL_SECONDS,
    vi_category: str = "competitive_intelligence",
    max_posts: int = 20,
) -> None:
    """
    Run the CI pipeline in a continuous background loop.

    Sleeps `interval_seconds` between runs (default: 86400 = 24h).
    First run executes immediately.

    Args:
        interval_seconds: seconds between pipeline runs
        vi_category:      VI archetype_memory category
        max_posts:        max posts to fingerprint per account
    """
    _log(f"CI Scheduler started — interval={interval_seconds}s ({interval_seconds/3600:.1f}h)")

    if _CI_TEST_MODE:
        _log("  TEST MODE — running once and exiting")
        try:
            run_ci_pipeline(vi_category=vi_category, max_posts=max_posts)
        except Exception as e:
            _log(f"  TEST MODE pipeline failed (non-fatal): {e}")
        return

    try:
        while True:
            _log(f"─── Cycle begin: {_now_iso()} ───")
            try:
                run_ci_pipeline(vi_category=vi_category, max_posts=max_posts)
            except Exception as e:
                _log(f"  CRITICAL: pipeline cycle failed: {e}")

            next_run = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=interval_seconds)
            _log(f"  Next run: {next_run.isoformat()} (in {interval_seconds/3600:.1f}h)")
            _log(f"─── Cycle end: {_now_iso()} ───")

            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        _log("CI Scheduler stopped by user (KeyboardInterrupt)")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="CI Scheduler — Competitive Intelligence background pipeline")
    ap.add_argument("--run",       action="store_true", help="Run pipeline once and exit")
    ap.add_argument("--loop",      action="store_true", help="Run in continuous background loop (24h interval)")
    ap.add_argument("--dry-run",   action="store_true", help="Run without persisting reports or feeding VI")
    ap.add_argument("--interval",  type=float, default=_DEFAULT_INTERVAL_SECONDS,
                    help=f"Seconds between cycles (default: {_DEFAULT_INTERVAL_SECONDS})")
    ap.add_argument("--max-posts", type=int, default=20, help="Max posts per account (default: 20)")
    ap.add_argument("--vi-category", default="competitive_intelligence", help="VI archetype_memory category")
    args = ap.parse_args()

    if args.dry_run:
        _log("DRY RUN MODE")
        os.environ["CI_TEST_MODE"] = "1"

    if args.loop:
        run_background_loop(
            interval_seconds=args.interval,
            vi_category=args.vi_category,
            max_posts=args.max_posts,
        )
    elif args.run or args.dry_run:
        summary = run_ci_pipeline(
            vi_category=args.vi_category,
            max_posts=args.max_posts,
        )
        print(json.dumps(summary, indent=2, default=str))
    else:
        ap.print_help()

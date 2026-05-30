#!/usr/bin/env python3
"""
bio_updater.py — Affiliate link distribution layer (bio/profile link).

Why this exists:
  - Instagram: links in post descriptions are NOT clickable
  - TikTok: same — only bio link is clickable
  - Solution: auto-update profile external_url when campaign changes

Strategy:
  - Instagram: instagrapi cl.account_edit(external_url=...) — API-native, stable
  - TikTok:    CDP Playwright (no public API) — same infra as tiktok_executor.py

Idempotency:
  - Read current bio link first
  - Only call API if link has changed (avoids rate limits, audit noise)
  - Returns BioUpdateResult with action="no_op" if unchanged

Policy:
  - Call ONCE per new campaign or new top product — NOT per post
  - Gate: only update if current link ≠ new link
  - Log every attempt (success, no_op, failure) to logs/bio_updates/YYYY-MM-DD.jsonl

Fail behavior:
  - NEVER blocks posting pipeline
  - On failure: logs error, returns BioUpdateResult.success=False
  - Caller decides whether to retry or proceed without bio update

ZERO AI calls. ZERO modification of Truth Layer.
"""

from __future__ import annotations

import datetime
import json
import sys
import threading
from dataclasses import dataclass, asdict
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

_LOG_DIR = _IMPERIO_ROOT / "logs" / "bio_updates"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()


# ── Result schema ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BioUpdateResult:
    """Result of a bio link update attempt."""
    platform:    str     # "instagram" | "tiktok"
    action:      str     # "updated" | "no_op" | "failed"
    old_url:     str     # previous bio link ("" if unknown)
    new_url:     str     # attempted URL
    success:     bool
    error:       str     # "" on success
    timestamp:   str

    def to_dict(self) -> dict:
        return asdict(self)


# ── Public API ────────────────────────────────────────────────────────────────

def update_bio_link(
    affiliate_url: str,
    platform:      str,
    force:         bool = False,   # skip idempotency check
) -> BioUpdateResult:
    """
    Update profile bio link to affiliate_url.

    Args:
        affiliate_url: full affiliate URL (must pass validate_tracked_url())
        platform:      "instagram" | "tiktok"
        force:         if True, update even if current link matches

    Returns:
        BioUpdateResult — always returns, never raises.
    """
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Validate URL has affiliate tracking params before touching any profile
    try:
        from revenue_layer.affiliate_link_builder import validate_tracked_url
        validate_tracked_url(affiliate_url)
    except ValueError as e:
        result = BioUpdateResult(
            platform=platform,
            action="failed",
            old_url="",
            new_url=affiliate_url,
            success=False,
            error=f"URL validation failed: {e}",
            timestamp=ts,
        )
        _log(result)
        return result

    platform_l = platform.lower()

    if platform_l == "instagram":
        result = _update_instagram(affiliate_url, force, ts)
    elif platform_l in ("tiktok", "tik_tok"):
        result = _update_tiktok(affiliate_url, force, ts)
    else:
        result = BioUpdateResult(
            platform=platform,
            action="failed",
            old_url="",
            new_url=affiliate_url,
            success=False,
            error=f"Unsupported platform: {platform!r}. Supported: instagram, tiktok",
            timestamp=ts,
        )

    _log(result)
    return result


def get_current_bio_link(platform: str) -> str:
    """
    Read current bio link for platform. Returns "" on failure.
    Used for idempotency check before update.
    """
    try:
        if platform.lower() == "instagram":
            return _get_instagram_bio_link()
        elif platform.lower() in ("tiktok", "tik_tok"):
            return _get_tiktok_bio_link()
    except Exception:
        pass
    return ""


# ── Instagram ─────────────────────────────────────────────────────────────────

def _update_instagram(url: str, force: bool, ts: str) -> BioUpdateResult:
    try:
        from instagrapi import Client
        cl = _get_instagram_client()

        current = _get_instagram_bio_link_from_client(cl)

        if not force and current == url:
            return BioUpdateResult(
                platform="instagram",
                action="no_op",
                old_url=current,
                new_url=url,
                success=True,
                error="",
                timestamp=ts,
            )

        cl.account_edit(external_url=url)

        return BioUpdateResult(
            platform="instagram",
            action="updated",
            old_url=current,
            new_url=url,
            success=True,
            error="",
            timestamp=ts,
        )

    except ImportError:
        return BioUpdateResult(
            platform="instagram",
            action="failed",
            old_url="",
            new_url=url,
            success=False,
            error="instagrapi not installed",
            timestamp=ts,
        )
    except Exception as e:
        return BioUpdateResult(
            platform="instagram",
            action="failed",
            old_url="",
            new_url=url,
            success=False,
            error=str(e)[:200],
            timestamp=ts,
        )


def _get_instagram_client():
    """Get authenticated instagrapi Client. Checks multiple session paths and formats."""
    from instagrapi import Client
    import json as _json

    _candidates = [
        _IMPERIO_ROOT.parent / "SYSTEM_FILES" / "SECURE_CREDENTIALS" / "instagram_session.json",
        _IMPERIO_ROOT.parent / "AI_TOOLS" / "browser_use" / "sessions" / "instagram_session.json",
    ]
    session_file = next((p for p in _candidates if p.exists()), None)
    if session_file is None:
        raise FileNotFoundError(
            f"Instagram session not found. Checked: {[str(p) for p in _candidates]}"
        )

    raw = _json.loads(session_file.read_text())
    cl = Client()

    cookies_val = raw.get("cookies")
    if isinstance(cookies_val, list):
        # Browser session format → list of cookie dicts [{name, value, ...}]
        sessionid = next(
            (c["value"] for c in cookies_val if c.get("name") == "sessionid"), None
        )
        if not sessionid:
            raise ValueError("sessionid cookie not found in browser session file")
        cl.login_by_sessionid(sessionid)
    else:
        # Instagrapi native format (cookies is a dict or absent; has uuids/device_settings)
        cl.load_settings(str(session_file))

    return cl


def _get_instagram_bio_link_from_client(cl) -> str:
    try:
        user = cl.account_info()
        return getattr(user, "external_url", "") or ""
    except Exception:
        return ""


def _get_instagram_bio_link() -> str:
    try:
        cl = _get_instagram_client()
        return _get_instagram_bio_link_from_client(cl)
    except Exception:
        return ""


# ── TikTok (CDP) ──────────────────────────────────────────────────────────────

def _update_tiktok(url: str, force: bool, ts: str) -> BioUpdateResult:
    """
    Update TikTok bio link via Chrome CDP (Playwright).
    TikTok has no public API for profile edit.
    """
    try:
        current = _get_tiktok_bio_link()

        if not force and current == url:
            return BioUpdateResult(
                platform="tiktok",
                action="no_op",
                old_url=current,
                new_url=url,
                success=True,
                error="",
                timestamp=ts,
            )

        _cdp_update_tiktok_bio(url)

        return BioUpdateResult(
            platform="tiktok",
            action="updated",
            old_url=current,
            new_url=url,
            success=True,
            error="",
            timestamp=ts,
        )

    except Exception as e:
        return BioUpdateResult(
            platform="tiktok",
            action="failed",
            old_url="",
            new_url=url,
            success=False,
            error=str(e)[:200],
            timestamp=ts,
        )


def _get_tiktok_bio_link() -> str:
    """Read current TikTok bio URL via CDP. Returns "" on failure."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp("http://localhost:9222")
            ctx     = browser.contexts[0]
            page    = ctx.new_page()
            page.goto("https://www.tiktok.com/setting", timeout=15000)
            page.wait_for_selector('input[name="website"]', timeout=8000)
            value = page.input_value('input[name="website"]')
            page.close()
            return value or ""
    except Exception:
        return ""


def _cdp_update_tiktok_bio(url: str) -> None:
    """
    Update TikTok profile website URL via CDP.
    Navigates to TikTok settings → profile → website field → save.
    Raises on failure.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp("http://localhost:9222")
        ctx     = browser.contexts[0]
        page    = ctx.new_page()

        try:
            page.goto("https://www.tiktok.com/setting", timeout=20000)
            page.wait_for_selector('input[name="website"]', timeout=10000)

            field = page.locator('input[name="website"]')
            field.triple_click()
            field.fill(url)

            # Save button — TikTok uses "Save" or checkmark
            save_btn = page.locator('button[type="submit"], button:has-text("Save")')
            save_btn.first.click(timeout=5000)
            page.wait_for_timeout(1500)  # brief settle

        finally:
            page.close()


# ── Logging ───────────────────────────────────────────────────────────────────

def _log(result: BioUpdateResult) -> None:
    date_str = datetime.date.today().isoformat()
    log_file = _LOG_DIR / f"{date_str}.jsonl"
    line     = json.dumps(result.to_dict(), ensure_ascii=False)
    with _lock:
        with open(log_file, "a") as f:
            f.write(line + "\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--url",      required=True, help="Affiliate URL to set in bio")
    parser.add_argument("--platform", required=True, choices=["instagram", "tiktok"])
    parser.add_argument("--force",    action="store_true", help="Skip idempotency check")
    args = parser.parse_args()

    result = update_bio_link(args.url, args.platform, force=args.force)
    print(json.dumps(result.to_dict(), indent=2))
    if result.action == "updated":
        print(f"\n✅ Bio link updated on {args.platform}")
    elif result.action == "no_op":
        print(f"\n— No change needed ({args.platform} bio already matches)")
    else:
        print(f"\n❌ Failed: {result.error}")

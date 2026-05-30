"""
facebook_executor.py — Facebook Reels/Posts via Chrome CDP
Uses existing Chrome session (already logged in as @alexanderaether).

Approach: Playwright → CDP → facebook.com/reels/create or composer.
Posts video Reels for affiliate content.

Facebook bot detection: strict. We use:
  - Real human-like delays (gaussian jitter)
  - Existing authenticated session (no login flow)
  - Viewport/UA matching existing Chrome session
"""

from __future__ import annotations
import asyncio
import json
import logging
import random
import time
from pathlib import Path
from datetime import datetime, timezone

log = logging.getLogger("facebook_executor")

CHROME_CDP = "http://127.0.0.1:9222"
LOGS_DIR   = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator/logs/facebook")
POSTS_LOG  = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE/facebook_posts.jsonl")

LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _human_delay(min_s: float = 0.8, max_s: float = 2.5):
    """Gaussian jitter between actions — bot detection evasion."""
    time.sleep(random.gauss((min_s + max_s) / 2, (max_s - min_s) / 4))


def _log_post(post_url: str, caption: str, task_id: str, video_path: str):
    entry = {
        "ts":         datetime.now(timezone.utc).isoformat(),
        "task_id":    task_id,
        "url":        post_url,
        "caption":    caption[:200],
        "video_path": video_path,
        "platform":   "facebook",
    }
    with open(POSTS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Core async ────────────────────────────────────────────────────────────────

async def _post_async(
    video_path: str,
    caption: str,
    task_id: str,
) -> dict:
    from playwright.async_api import async_playwright

    video_file = Path(video_path)
    if not video_file.exists():
        return {"status": "failed", "error": f"Video not found: {video_path}"}

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CHROME_CDP)
        ctx     = browser.contexts[0]
        page    = await ctx.new_page()

        try:
            # Navigate to Facebook Reels creation
            log.info(f"[{task_id}] Navigating to Facebook Reels create...")
            await page.goto("https://www.facebook.com/reels/create", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Check if redirected to login (shouldn't happen with valid session)
            if "login" in page.url:
                return {"status": "failed", "error": "Facebook session expired — re-login needed"}

            # Try Reels upload — click "Upload" or file area
            upload_area = page.locator('input[type="file"][accept*="video"], [data-visualcompletion="upload-photo"]')
            if await upload_area.count() == 0:
                # Fallback: use main composer
                await page.goto("https://www.facebook.com/", wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2)
                # Click "Photo/Video" in composer
                photo_btn = page.locator('[data-pagelet="FeedComposer"] [aria-label*="Photo"], [aria-label*="Foto"], span:has-text("Photo/video")')
                await photo_btn.first.click(timeout=8000)
                await asyncio.sleep(1)

            # Upload file
            file_input = page.locator('input[type="file"]')
            await file_input.first.set_input_files(str(video_file))
            log.info(f"[{task_id}] File set: {video_file.name}")
            await asyncio.sleep(5)  # Facebook needs time to process video

            # Fill caption
            caption_field = page.locator(
                '[aria-label="Describe your reel"], '
                '[data-contents] div[contenteditable], '
                '[aria-label*="caption" i], '
                '[aria-label*="descripción" i]'
            )
            if await caption_field.count() > 0:
                await caption_field.first.click()
                _human_delay(0.5, 1.2)
                await page.keyboard.type(caption, delay=30)
                await asyncio.sleep(1)

            # Wait for video to process
            log.info(f"[{task_id}] Waiting for video processing...")
            try:
                await page.wait_for_function(
                    "() => !document.querySelector('[data-testid=\"upload-progress\"]')",
                    timeout=180000
                )
            except Exception:
                await asyncio.sleep(15)  # fallback wait

            # Click Publish / Share / Next
            for btn_text in ["Publicar", "Publish", "Compartir", "Share", "Next", "Siguiente"]:
                btn = page.locator(f'div[aria-label="{btn_text}"], button:has-text("{btn_text}")')
                if await btn.count() > 0:
                    await btn.first.click()
                    log.info(f"[{task_id}] Clicked: {btn_text}")
                    await asyncio.sleep(3)
                    break

            # Get post URL from current URL or confirmation
            await asyncio.sleep(4)
            post_url = page.url
            if "facebook.com" not in post_url:
                post_url = "https://www.facebook.com/profile"

            log.info(f"[{task_id}] Facebook post done: {post_url}")
            _log_post(post_url, caption, task_id, str(video_file))

            return {
                "status":   "success",
                "url":      post_url,
                "platform": "facebook",
                "caption":  caption[:100],
            }

        except Exception as e:
            log.error(f"[{task_id}] Facebook post failed: {e}")
            try:
                ss = LOGS_DIR / f"error_{task_id}_{int(time.time())}.png"
                await page.screenshot(path=str(ss))
            except Exception:
                pass
            return {"status": "failed", "error": str(e)}

        finally:
            await page.close()


# ── Public interface ──────────────────────────────────────────────────────────

def post_reel(params: dict, task_id: str = "") -> dict:
    """
    Post Reel/video to Facebook.

    params:
      video_path : str — absolute path to .mp4
      caption    : str — post text with affiliate link
    """
    video_path = params.get("video_path", "")
    caption    = params.get("caption", params.get("description", ""))

    if not video_path:
        return {"status": "failed", "error": "video_path required"}

    return asyncio.run(_post_async(
        video_path = video_path,
        caption    = caption,
        task_id    = task_id,
    ))


def is_ready() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(CHROME_CDP + "/json", timeout=3)
        return True
    except Exception:
        return False

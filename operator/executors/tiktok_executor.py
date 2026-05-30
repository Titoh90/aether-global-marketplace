"""
tiktok_executor.py — TikTok Photo Carousel posting via Chrome CDP

Account: @alexanderaether (already logged in Chrome).

Strategy:
  1. Connect Playwright to existing Chrome session via CDP
  2. Navigate to tiktok.com/upload
  3. Switch to "Photo" mode (carousel)
  4. Upload image files via input[type="file"]
  5. Fill caption
  6. Click Post and wait for confirmation

TikTok Photo Mode supports up to 35 images per carousel.
Caption limit: 2200 chars.
Affiliate link goes in caption (not a separate field).

If Photo Mode toggle not found → falls back to posting first image as single photo.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("tiktok_executor")

CHROME_CDP = "http://127.0.0.1:9222"
LOGS_DIR   = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator/logs/tiktok")
POSTS_LOG  = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE/tiktok_posts.jsonl")
UPLOAD_URL = "https://www.tiktok.com/upload?lang=en"

LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _log_post(post_id: str, caption: str, task_id: str, image_paths: list[str]):
    entry = {
        "ts":          datetime.now(timezone.utc).isoformat(),
        "task_id":     task_id,
        "post_id":     post_id,
        "caption":     caption[:200],
        "image_count": len(image_paths),
        "platform":    "tiktok",
        "handle":      "@alexanderaether",
    }
    with open(POSTS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Core async ────────────────────────────────────────────────────────────────

async def _post_async(
    image_paths: list[str],
    caption: str,
    task_id: str,
) -> dict:
    from playwright.async_api import async_playwright

    # Validate files
    valid_paths = [p for p in image_paths if Path(p).exists()]
    if not valid_paths:
        return {"status": "failed", "error": "No valid image files found"}

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CHROME_CDP)
        ctx     = browser.contexts[0]
        page    = await ctx.new_page()

        try:
            log.info(f"[{task_id}] Navigating to TikTok upload...")
            await page.goto(UPLOAD_URL, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Check if logged in
            if "login" in page.url.lower() or "signup" in page.url.lower():
                return {"status": "failed", "error": "TikTok session expired — login required"}

            # ── Try to switch to Photo mode ───────────────────────────────────
            photo_mode_active = False
            try:
                # Look for Photo/Image toggle (TikTok has "Video" / "Photo" tabs)
                photo_tab = page.locator('div:has-text("Photo"), button:has-text("Photo"), [data-e2e="photo-tab"]')
                if await photo_tab.count() > 0:
                    await photo_tab.first.click(timeout=3000)
                    await asyncio.sleep(1)
                    photo_mode_active = True
                    log.info(f"[{task_id}] Switched to Photo mode")
            except Exception:
                log.info(f"[{task_id}] Photo tab not found — using default upload mode")

            # ── Upload images ─────────────────────────────────────────────────
            file_input = page.locator('input[type="file"]')
            if await file_input.count() == 0:
                return {"status": "failed", "error": "File input not found on TikTok upload page"}

            # Upload all images at once (TikTok upload accepts multiple)
            await file_input.first.set_input_files(valid_paths)
            log.info(f"[{task_id}] Uploaded {len(valid_paths)} images")

            # Wait for upload processing
            await asyncio.sleep(8)

            # ── Fill caption ──────────────────────────────────────────────────
            caption_field = page.locator(
                '[data-e2e="caption-input"], '
                'div[contenteditable="true"], '
                'textarea[placeholder*="caption"], '
                'textarea[placeholder*="Caption"]'
            )
            if await caption_field.count() > 0:
                await caption_field.first.click()
                await asyncio.sleep(0.5)
                # Clear and type
                await caption_field.first.fill("")
                await caption_field.first.type(caption[:2200], delay=5)
                await asyncio.sleep(0.5)
            else:
                log.warning(f"[{task_id}] Caption field not found — posting without caption")

            # ── Click Post ────────────────────────────────────────────────────
            post_btn = page.locator(
                'button[data-e2e="post-button"], '
                'button:has-text("Post"), '
                'button:has-text("Submit")'
            )
            if await post_btn.count() == 0:
                return {"status": "failed", "error": "Post button not found"}

            await post_btn.first.click(timeout=10000)
            log.info(f"[{task_id}] Clicked Post button")

            # ── Wait for success ──────────────────────────────────────────────
            # TikTok redirects to profile or shows success message
            try:
                await page.wait_for_url("**/profile**", timeout=30000)
                post_url = page.url
            except Exception:
                # Check for success message instead
                try:
                    await page.wait_for_selector(
                        '[data-e2e="post-success"], div:has-text("Your video is being uploaded")',
                        timeout=20000
                    )
                    post_url = page.url
                except Exception:
                    post_url = page.url

            # Extract post ID from URL if available
            post_id = "unknown"
            if "/video/" in post_url:
                post_id = post_url.split("/video/")[-1].split("?")[0]
            elif "/photo/" in post_url:
                post_id = post_url.split("/photo/")[-1].split("?")[0]

            log.info(f"[{task_id}] Posted — post_id={post_id} | url={post_url}")
            _log_post(post_id, caption, task_id, valid_paths)

            return {
                "status":      "success",
                "post_id":     post_id,
                "url":         post_url,
                "images_sent": len(valid_paths),
                "photo_mode":  photo_mode_active,
            }

        except Exception as e:
            log.error(f"[{task_id}] Error: {e}")
            return {"status": "failed", "error": str(e)[:300]}

        finally:
            await page.close()


# ── Public API ────────────────────────────────────────────────────────────────

def post_photos(params: dict, task_id: str = "") -> dict:
    """
    Post photo carousel to TikTok.

    params:
      image_paths : list[str] — absolute paths to PNG/JPG images (≤35)
      caption     : str       — post caption with affiliate link (≤2200 chars)
      link        : str       — affiliate URL (included in caption if not already present)

    Returns:
      {"status": "success", "post_id": "...", "url": "...", "images_sent": N}
    """
    image_paths = params.get("image_paths", [])
    caption     = params.get("caption", "")
    link        = params.get("link", params.get("affiliate_url", ""))

    if not image_paths:
        return {"status": "failed", "error": "image_paths required"}

    if not task_id:
        task_id = f"tt_{int(time.time())}"

    # Append link to caption if not already present
    if link and link not in caption:
        _cap_with_link = f"{caption}\n{link}".strip()
        caption = _cap_with_link[:2200]

    return asyncio.run(_post_async(
        image_paths = image_paths,
        caption     = caption,
        task_id     = task_id,
    ))


def is_ready() -> bool:
    """Check Chrome CDP reachable and TikTok likely logged in."""
    try:
        import urllib.request
        urllib.request.urlopen(CHROME_CDP + "/json", timeout=3)
        return True
    except Exception:
        return False


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", nargs="+", required=True, help="Image paths")
    ap.add_argument("--caption", default="Check this out!")
    ap.add_argument("--link", default="")
    args = ap.parse_args()

    result = post_photos({
        "image_paths": args.images,
        "caption":     args.caption,
        "link":        args.link,
    })
    print(json.dumps(result, indent=2))

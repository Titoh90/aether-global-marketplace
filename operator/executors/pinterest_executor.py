"""
pinterest_executor.py — Pinterest Pin/Idea Pin creation via Chrome CDP
Account: @aetherventuresoficial (already logged in Chrome).

Approach: Playwright → CDP → pinterest.com/pin-creation-tool/
Creates video Pins or image Pins with affiliate links.

Pinterest is affiliate-friendly:
  - Direct links allowed (no link-in-bio restriction)
  - High-intent audience (product research mindset)
  - Evergreen traffic (pins resurface months later)
"""

from __future__ import annotations
import asyncio, json, logging, time
from pathlib import Path
from datetime import datetime, timezone

log = logging.getLogger("pinterest_executor")

CHROME_CDP   = "http://127.0.0.1:9222"
LOGS_DIR     = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator/logs/pinterest")
POSTS_LOG    = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE/pinterest_posts.jsonl")
PIN_CREATE   = "https://www.pinterest.com/pin-creation-tool/"

LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _log_post(pin_url: str, title: str, link: str, task_id: str, media_path: str):
    entry = {
        "ts":         datetime.now(timezone.utc).isoformat(),
        "task_id":    task_id,
        "url":        pin_url,
        "title":      title,
        "link":       link,
        "media_path": media_path,
        "platform":   "pinterest",
    }
    with open(POSTS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ── Core async ────────────────────────────────────────────────────────────────

async def _pin_async(
    media_path: str,
    title: str,
    description: str,
    link: str,
    board: str,
    task_id: str,
) -> dict:
    from playwright.async_api import async_playwright

    media_file = Path(media_path)
    if not media_file.exists():
        return {"status": "failed", "error": f"Media not found: {media_path}"}

    is_video = media_file.suffix.lower() in [".mp4", ".mov", ".m4v"]

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(CHROME_CDP)
        ctx     = browser.contexts[0]
        page    = await ctx.new_page()

        try:
            log.info(f"[{task_id}] Opening Pinterest pin creation tool...")
            await page.goto(PIN_CREATE, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            if "login" in page.url or "signup" in page.url:
                return {"status": "failed", "error": "Pinterest session expired"}

            # Upload media
            file_input = page.locator('input[type="file"]')
            await file_input.first.set_input_files(str(media_file))
            log.info(f"[{task_id}] Uploaded: {media_file.name}")
            await asyncio.sleep(5 if is_video else 2)

            # Title
            title_field = page.locator('[data-test-id="pin-draft-title"], input[placeholder*="title" i], input[placeholder*="título" i]')
            if await title_field.count() > 0:
                await title_field.first.fill(title[:100])
                await asyncio.sleep(0.5)

            # Description
            desc_field = page.locator(
                '[data-test-id="pin-draft-description"], '
                'textarea[placeholder*="description" i], '
                'div[data-placeholder*="description" i]'
            )
            if await desc_field.count() > 0:
                await desc_field.first.fill(description[:500])
                await asyncio.sleep(0.5)

            # Destination link (affiliate URL)
            link_field = page.locator(
                '[data-test-id="pin-draft-link"], '
                'input[placeholder*="link" i], '
                'input[placeholder*="enlace" i]'
            )
            if await link_field.count() > 0 and link:
                await link_field.first.fill(link)
                await asyncio.sleep(0.5)

            # Board selection
            if board:
                board_btn = page.locator('[data-test-id="board-dropdown-select-button"], [aria-label*="board" i]')
                if await board_btn.count() > 0:
                    await board_btn.first.click()
                    await asyncio.sleep(1)
                    board_opt = page.locator(f'[data-test-id="board-row"]:has-text("{board}")')
                    if await board_opt.count() > 0:
                        await board_opt.first.click()
                        await asyncio.sleep(0.5)

            # Publish
            publish_btn = page.locator(
                '[data-test-id="board-dropdown-save-button"], '
                'button:has-text("Publish"), '
                'button:has-text("Publicar"), '
                'button:has-text("Save")'
            )
            await publish_btn.first.click(timeout=10000)
            log.info(f"[{task_id}] Pin published")
            await asyncio.sleep(4)

            # Get pin URL
            pin_url = page.url
            if "pin-creation" in pin_url:
                # Not navigated yet — extract from page
                pin_link = page.locator('a[href*="/pin/"]')
                if await pin_link.count() > 0:
                    pin_url = "https://www.pinterest.com" + await pin_link.first.get_attribute("href")

            _log_post(pin_url, title, link, task_id, str(media_file))

            return {
                "status":   "success",
                "url":      pin_url,
                "platform": "pinterest",
                "title":    title,
                "link":     link,
            }

        except Exception as e:
            log.error(f"[{task_id}] Pinterest pin failed: {e}")
            try:
                ss = LOGS_DIR / f"error_{task_id}_{int(time.time())}.png"
                await page.screenshot(path=str(ss))
            except Exception:
                pass
            return {"status": "failed", "error": str(e)}

        finally:
            await page.close()


# ── Public interface ──────────────────────────────────────────────────────────

def create_pin(params: dict, task_id: str = "") -> dict:
    """
    Create Pin on Pinterest.

    params:
      media_path  : str — path to image (.jpg/.png) or video (.mp4)
      title       : str — pin title (≤100 chars)
      description : str — pin description
      link        : str — destination URL (affiliate link)
      board       : str — board name (optional, uses default)
    """
    media_path  = params.get("media_path", params.get("video_path", params.get("image_path", "")))
    title       = params.get("title", "")
    description = params.get("description", params.get("caption", ""))
    link        = params.get("link", params.get("affiliate_url", ""))
    board       = params.get("board", "")

    if not media_path:
        return {"status": "failed", "error": "media_path required"}

    return asyncio.run(_pin_async(
        media_path  = media_path,
        title       = title,
        description = description,
        link        = link,
        board       = board,
        task_id     = task_id,
    ))


def is_ready() -> bool:
    try:
        import urllib.request
        urllib.request.urlopen(CHROME_CDP + "/json", timeout=3)
        return True
    except Exception:
        return False

"""
youtube_executor.py — YouTube Shorts/Video upload via Chrome CDP
Uses existing Chrome session (already logged in as @alexanderaether).

Approach: Playwright connects to Chrome :9222 via CDP → navigates
YouTube Studio upload flow → sets metadata → publishes.

Supports: Shorts (≤60s vertical) and standard videos.
Output: youtube post URL + video_id.
"""

from __future__ import annotations
import asyncio, json, logging, os, time
from pathlib import Path
from datetime import datetime, timezone

log = logging.getLogger("youtube_executor")

CHROME_CDP    = "http://127.0.0.1:9222"
LOGS_DIR      = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator/logs/youtube")
POSTS_LOG     = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE/youtube_posts.jsonl")
STUDIO_URL    = "https://studio.youtube.com"

LOGS_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _log_post(video_id: str, title: str, url: str, task_id: str, video_path: str):
    entry = {
        "ts":         datetime.now(timezone.utc).isoformat(),
        "task_id":    task_id,
        "video_id":   video_id,
        "title":      title,
        "url":        url,
        "video_path": video_path,
        "platform":   "youtube",
    }
    with open(POSTS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    log.info(f"[{task_id}] YouTube post logged: {url}")


# ── Core async upload ─────────────────────────────────────────────────────────

async def _upload_async(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    is_short: bool,
    task_id: str,
    made_for_kids: bool = False,
    visibility: str = "public",   # public | unlisted | private
) -> dict:
    from playwright.async_api import async_playwright

    video_file = Path(video_path)
    if not video_file.exists():
        return {"status": "failed", "error": f"Video not found: {video_path}"}

    async with async_playwright() as p:
        browser   = await p.chromium.connect_over_cdp(CHROME_CDP)
        ctx       = browser.contexts[0]
        page      = await ctx.new_page()

        try:
            log.info(f"[{task_id}] Navigating to YouTube Studio...")
            await page.goto(STUDIO_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Click CREATE button
            create_btn = page.locator('button[aria-label="Crear"], ytcp-button#create-icon, [aria-label="Create"]')
            await create_btn.first.click(timeout=10000)
            await asyncio.sleep(1)

            # Click "Upload videos"
            upload_opt = page.locator('tp-yt-paper-item:has-text("Subir videos"), tp-yt-paper-item:has-text("Upload videos")')
            await upload_opt.first.click(timeout=8000)
            await asyncio.sleep(1)

            # File input upload
            file_input = page.locator('input[type="file"]')
            await file_input.set_input_files(str(video_file))
            log.info(f"[{task_id}] File set: {video_file.name} ({video_file.stat().st_size//1024}KB)")

            # Wait for upload dialog to appear
            await page.wait_for_selector('ytcp-uploads-dialog, #dialog', timeout=20000)
            await asyncio.sleep(3)

            # Fill title (clear existing first)
            title_field = page.locator('#title-textarea div[contenteditable], ytcp-social-suggestions-textbox #title-textarea')
            await title_field.first.click()
            await page.keyboard.press("Control+A")
            await page.keyboard.type(title[:100])  # YT title limit 100 chars
            await asyncio.sleep(1)

            # Fill description
            desc_field = page.locator('#description-textarea div[contenteditable]')
            if await desc_field.count() > 0:
                await desc_field.first.click()
                await page.keyboard.press("Control+A")
                await page.keyboard.type(description[:5000])
                await asyncio.sleep(1)

            # Not made for kids
            kids_no = page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"], #is-video-made-for-kids-id-not')
            if await kids_no.count() > 0 and not made_for_kids:
                await kids_no.first.click()

            # NEXT → NEXT → NEXT (3 times through wizard)
            for step in range(3):
                next_btn = page.locator('ytcp-button#next-button, button:has-text("Siguiente"), button:has-text("Next")')
                if await next_btn.count() > 0:
                    await next_btn.first.click()
                    await asyncio.sleep(2)

            # Set visibility
            vis_map = {"public": "PUBLIC", "unlisted": "UNLISTED", "private": "PRIVATE"}
            vis_val = vis_map.get(visibility, "PUBLIC")
            vis_radio = page.locator(f'tp-yt-paper-radio-button[name="{vis_val}"]')
            if await vis_radio.count() > 0:
                await vis_radio.first.click()
                await asyncio.sleep(1)

            # Wait for upload to complete (progress bar disappears)
            log.info(f"[{task_id}] Waiting for upload to complete...")
            try:
                await page.wait_for_selector(
                    'ytcp-video-upload-progress[upload-state="complete"], span:has-text("Upload complete"), span:has-text("Subida completa")',
                    timeout=300000  # 5 min max
                )
            except Exception:
                log.warning(f"[{task_id}] Upload progress selector timeout — proceeding anyway")
            await asyncio.sleep(2)

            # Click PUBLISH / SAVE
            publish_btn = page.locator('ytcp-button#done-button, button:has-text("Publicar"), button:has-text("Publish"), button:has-text("Save")')
            await publish_btn.first.click(timeout=15000)
            await asyncio.sleep(3)

            # Extract video URL from confirmation dialog
            video_url  = ""
            video_id   = ""
            link_elem = page.locator('a[href*="youtu.be"], a[href*="youtube.com/watch"]')
            if await link_elem.count() > 0:
                video_url = await link_elem.first.get_attribute("href")
                if "youtu.be/" in video_url:
                    video_id = video_url.split("youtu.be/")[-1].split("?")[0]
                elif "v=" in video_url:
                    video_id = video_url.split("v=")[-1].split("&")[0]

            if not video_url:
                video_url = f"{STUDIO_URL}/videos"  # fallback to studio

            log.info(f"[{task_id}] Published: {video_url}")
            _log_post(video_id, title, video_url, task_id, str(video_file))

            return {
                "status":     "success",
                "video_id":   video_id,
                "url":        video_url,
                "title":      title,
                "platform":   "youtube",
                "is_short":   is_short,
            }

        except Exception as e:
            log.error(f"[{task_id}] YouTube upload failed: {e}")
            # Screenshot for debug
            try:
                ss_path = LOGS_DIR / f"error_{task_id}_{int(time.time())}.png"
                await page.screenshot(path=str(ss_path))
                log.info(f"[{task_id}] Screenshot: {ss_path}")
            except Exception:
                pass
            return {"status": "failed", "error": str(e)}

        finally:
            await page.close()


# ── Public interface ──────────────────────────────────────────────────────────

def post_video(params: dict, task_id: str = "") -> dict:
    """
    Post video to YouTube.

    params:
      video_path  : str  — absolute path to .mp4
      title       : str  — video title (≤100 chars)
      description : str  — full description with affiliate links
      tags        : list — optional tags
      is_short    : bool — True if vertical ≤60s (auto-detected if omitted)
      visibility  : str  — "public" | "unlisted" | "private" (default: public)
    """
    video_path  = params.get("video_path", "")
    title       = params.get("title", "Check this out!")
    description = params.get("description", params.get("caption", ""))
    tags        = params.get("tags", [])
    visibility  = params.get("visibility", "public")

    # Auto-detect Short: vertical video ≤60s → add #Shorts to title
    is_short = params.get("is_short", False)
    if not is_short and video_path:
        try:
            import subprocess
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_streams", video_path],
                capture_output=True, text=True
            )
            info = json.loads(probe.stdout)
            for s in info.get("streams", []):
                dur = float(s.get("duration", 99))
                w   = s.get("width", 1)
                h   = s.get("height", 1)
                if dur <= 60 and h > w:
                    is_short = True
                    break
        except Exception:
            pass

    if is_short and "#Shorts" not in title:
        title = title[:93] + " #Shorts"

    return asyncio.run(_upload_async(
        video_path   = video_path,
        title        = title,
        description  = description,
        tags         = tags,
        is_short     = is_short,
        task_id      = task_id,
        visibility   = visibility,
    ))


def is_ready() -> bool:
    """Check Chrome CDP is reachable."""
    try:
        import urllib.request
        urllib.request.urlopen(CHROME_CDP + "/json", timeout=3)
        return True
    except Exception:
        return False

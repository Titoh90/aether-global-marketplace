"""
twitter_executor.py — X (Twitter) post via Chrome CDP + cookie injection
Account: @AAether32355 (cookies saved at SYSTEM_FILES/cookies/x_cookies.json).

Strategy:
  1. Load saved cookies into Playwright context connected to Chrome CDP
  2. Navigate to x.com/compose/tweet (or use API if keys available)
  3. Type tweet + attach media → Tweet button

Twitter is the easiest: short content, fast upload, no processing wait.
Video limit: 512MB, 2min20s. Image: up to 4 per tweet.
"""

from __future__ import annotations
import asyncio, json, logging, time
from pathlib import Path
from datetime import datetime, timezone

log = logging.getLogger("twitter_executor")

CHROME_CDP   = "http://127.0.0.1:9222"
COOKIES_FILE = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/SYSTEM_FILES/cookies/x_cookies.json")
LOGS_DIR     = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator/logs/twitter")
POSTS_LOG    = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE/twitter_posts.jsonl")

LOGS_DIR.mkdir(parents=True, exist_ok=True)

TWEET_CHAR_LIMIT = 280


def _log_post(tweet_url: str, text: str, task_id: str, media_path: str = ""):
    entry = {
        "ts":         datetime.now(timezone.utc).isoformat(),
        "task_id":    task_id,
        "url":        tweet_url,
        "text":       text[:280],
        "media_path": media_path,
        "platform":   "twitter",
        "handle":     "@AAether32355",
    }
    with open(POSTS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _load_cookies() -> list[dict]:
    """Load saved X session cookies."""
    if not COOKIES_FILE.exists():
        return []
    with open(COOKIES_FILE) as f:
        return json.load(f)


# ── Core async ────────────────────────────────────────────────────────────────

async def _tweet_async(
    text: str,
    media_path: str,
    task_id: str,
    reply_to: str = "",
) -> dict:
    from playwright.async_api import async_playwright

    # Truncate to char limit
    if len(text) > TWEET_CHAR_LIMIT:
        text = text[:TWEET_CHAR_LIMIT - 3] + "..."

    media_file = Path(media_path) if media_path else None
    if media_file and not media_file.exists():
        log.warning(f"[{task_id}] Media not found: {media_path} — posting text only")
        media_file = None

    async with async_playwright() as p:
        # Try CDP first (uses existing Chrome session)
        try:
            browser = await p.chromium.connect_over_cdp(CHROME_CDP)
            ctx     = browser.contexts[0]
            # Inject fresh cookies into existing context
            saved_cookies = _load_cookies()
            if saved_cookies:
                await ctx.add_cookies(saved_cookies)
        except Exception as e:
            log.warning(f"[{task_id}] CDP connect failed: {e} — launching fresh browser")
            browser = await p.chromium.launch(headless=False)
            ctx     = await browser.new_context()
            saved_cookies = _load_cookies()
            if saved_cookies:
                await ctx.add_cookies(saved_cookies)

        page = await ctx.new_page()

        try:
            url = f"https://x.com/compose/tweet"
            if reply_to:
                url = f"https://x.com/intent/tweet?in_reply_to={reply_to}"

            log.info(f"[{task_id}] Navigating to X compose...")
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)

            if "login" in page.url or "signin" in page.url:
                return {"status": "failed", "error": "X session expired — re-extract cookies needed"}

            # Find tweet text area
            tweet_box = page.locator(
                '[data-testid="tweetTextarea_0"], '
                'div[aria-label*="Tweet text" i], '
                'div[aria-label*="Post text" i], '
                'div[contenteditable="true"][data-testid*="tweet" i]'
            )
            await tweet_box.first.click(timeout=10000)
            await asyncio.sleep(0.5)
            await page.keyboard.type(text, delay=25)
            await asyncio.sleep(0.8)

            # Attach media if provided
            if media_file:
                file_input = page.locator('input[data-testid="fileInput"], input[type="file"][accept*="image"]')
                if await file_input.count() > 0:
                    await file_input.first.set_input_files(str(media_file))
                    log.info(f"[{task_id}] Media attached: {media_file.name}")
                    await asyncio.sleep(3)  # Wait for upload indicator
                else:
                    # Click the media button
                    media_btn = page.locator('[data-testid="attachments"], [aria-label*="media" i], [aria-label*="imagen" i]')
                    if await media_btn.count() > 0:
                        await media_btn.first.click()
                        await asyncio.sleep(1)
                        file_input2 = page.locator('input[type="file"]')
                        await file_input2.first.set_input_files(str(media_file))
                        await asyncio.sleep(3)

            # Wait for media to upload
            if media_file:
                try:
                    await page.wait_for_function(
                        "() => !document.querySelector('[data-testid=\"progressBar\"]')",
                        timeout=60000
                    )
                except Exception:
                    await asyncio.sleep(5)

            # Click Tweet / Post button
            tweet_btn = page.locator(
                '[data-testid="tweetButtonInline"], '
                '[data-testid="tweetButton"], '
                'div[aria-label="Tweet"], '
                'div[aria-label="Post"]'
            )
            await tweet_btn.first.click(timeout=10000)
            log.info(f"[{task_id}] Tweet sent")
            await asyncio.sleep(3)

            # Get tweet URL — navigate to profile to find latest tweet
            tweet_url = f"https://x.com/AAether32355"
            try:
                await page.goto(tweet_url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(2)
                # Get first tweet link
                first_tweet = page.locator('article a[href*="/status/"]')
                if await first_tweet.count() > 0:
                    href = await first_tweet.first.get_attribute("href")
                    tweet_url = "https://x.com" + href
            except Exception:
                pass

            _log_post(tweet_url, text, task_id, str(media_file) if media_file else "")

            return {
                "status":   "success",
                "url":      tweet_url,
                "platform": "twitter",
                "text":     text,
            }

        except Exception as e:
            log.error(f"[{task_id}] Tweet failed: {e}")
            try:
                ss = LOGS_DIR / f"error_{task_id}_{int(time.time())}.png"
                await page.screenshot(path=str(ss))
            except Exception:
                pass
            return {"status": "failed", "error": str(e)}

        finally:
            await page.close()


# ── Public interface ──────────────────────────────────────────────────────────

def post_tweet(params: dict, task_id: str = "") -> dict:
    """
    Post tweet to X.

    params:
      text       : str — tweet text (auto-truncated to 280)
      media_path : str — optional path to image/video
      reply_to   : str — optional tweet ID to reply to
    """
    text       = params.get("text", params.get("caption", ""))
    media_path = params.get("media_path", params.get("video_path", params.get("image_path", "")))
    reply_to   = params.get("reply_to", "")

    if not text:
        return {"status": "failed", "error": "text required"}

    return asyncio.run(_tweet_async(
        text       = text,
        media_path = media_path,
        task_id    = task_id,
        reply_to   = reply_to,
    ))


def refresh_cookies() -> dict:
    """Re-extract X cookies from Chrome and save to file."""
    async def _refresh():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(CHROME_CDP)
            ctx     = browser.contexts[0]
            cookies = await ctx.cookies(["https://x.com", "https://twitter.com"])
            with open(COOKIES_FILE, "w") as f:
                json.dump(cookies, f, indent=2)
            auth = next((c for c in cookies if c['name'] == 'auth_token'), None)
            return {"status": "success", "count": len(cookies), "has_auth": auth is not None}
    return asyncio.run(_refresh())


def is_ready() -> bool:
    """Check Chrome CDP reachable and cookies file exists."""
    try:
        import urllib.request
        urllib.request.urlopen(CHROME_CDP + "/json", timeout=3)
        return COOKIES_FILE.exists()
    except Exception:
        return False

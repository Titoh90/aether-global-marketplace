"""
BROWSER EXECUTOR — browser-use v0.12.6 wrapper for IMPERIO Operator
Connects to REAL Chrome via CDP (port 9222).
Uses Ollama qwen2.5:1.5b LOCAL — no API cost.

Limitations (documented, not hidden):
- Fiverr/protected sites: reCAPTCHA blocks extraction
- qwen2.5:1.5b: good for simple navigation, struggles with complex multi-step
- CDP session: shared with Flow Director Chrome instance

Suitable tasks (tested):
- Google search + extract results
- Amazon product info (if logged in Chrome session)
- Public pages without captcha
"""

import asyncio
import logging
import time
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

log = logging.getLogger("browser_executor")

CDP_URL        = "http://localhost:9223"   # dedicated Chrome, no conflict with Flow Director (:9222)
OLLAMA_MODEL   = "qwen2.5:7b"             # upgraded from 1.5b — no more DOM analysis timeouts
OLLAMA_HOST    = "http://localhost:11434"
SCREENSHOTS    = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/BROWSER_OPERATOR/screenshots")
LOGS_DIR       = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/BROWSER_OPERATOR/logs")
MAX_STEPS      = 12


def chrome_cdp_active() -> bool:
    import socket
    try:
        s = socket.create_connection(("127.0.0.1", 9223), timeout=1)
        s.close()
        return True
    except:
        return False


async def _run_browser_task(task: str, task_id: str) -> dict:
    """Core async browser-use execution."""
    from browser_use import Agent
    from browser_use.browser.profile import BrowserProfile
    from browser_use.browser.session import BrowserSession
    from browser_use.llm.ollama.chat import ChatOllama

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    SCREENSHOTS.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    llm = ChatOllama(model=OLLAMA_MODEL, host=OLLAMA_HOST)

    profile = BrowserProfile(
        cdp_url=CDP_URL,
        headless=False,
        keep_alive=True,     # Don't kill Chrome when done
        disable_security=True,
    )

    browser_session = BrowserSession(browser_profile=profile)

    conv_path = str(LOGS_DIR / f"conv_{task_id}_{ts}.json")
    agent = Agent(
        task=task,
        llm=llm,
        browser_session=browser_session,
        save_conversation_path=conv_path,
    )

    start = time.time()
    result = await agent.run(max_steps=MAX_STEPS)
    elapsed = round(time.time() - start, 1)

    # Extract result text
    final_text = ""
    if hasattr(result, 'final_result'):
        final_text = result.final_result() or ""
    elif hasattr(result, 'history'):
        for item in reversed(result.history):
            if hasattr(item, 'result') and item.result:
                final_text = str(item.result)
                break

    # Screenshot via CDP directly (avoid API version issues)
    screenshot_path = None
    try:
        page = await browser_session.get_current_page()
        screenshot_bytes = await page.screenshot()
        screenshot_path = str(SCREENSHOTS / f"browser_{task_id}_{ts}.png")
        Path(screenshot_path).write_bytes(screenshot_bytes)
    except Exception as e:
        log.warning(f"Screenshot failed: {e}")

    return {
        "status": "success",
        "task_id": task_id,
        "task": task,
        "final_result": final_text,
        "elapsed_s": elapsed,
        "screenshot": screenshot_path,
        "conversation_log": conv_path,
        "model": OLLAMA_MODEL,
        "cdp_url": CDP_URL,
    }


def browse(task: str, task_id: str) -> dict:
    """
    Synchronous wrapper. Executes browser task via real Chrome.
    Returns result dict with status/result/screenshot.
    """
    if not chrome_cdp_active():
        return {
            "status": "failed",
            "error": (
                "Chrome CDP no activo en :9223 (browser-use port). "
                "Launch: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome "
                "--remote-debugging-port=9223 --user-data-dir=/tmp/chrome_browser_use"
            ),
            "task_id": task_id
        }

    log.info(f"Browser task: {task[:80]}...")

    try:
        result = asyncio.run(_run_browser_task(task, task_id))
        return result
    except Exception as e:
        log.exception(f"Browser task failed: {e}")
        return {
            "status": "failed",
            "error": str(e)[:500],
            "task_id": task_id
        }


# Known captcha sites — warn before attempting
CAPTCHA_LIKELY = ["fiverr.com", "upwork.com", "linkedin.com", "cloudflare"]


def captcha_risk(task: str) -> bool:
    return any(site in task.lower() for site in CAPTCHA_LIKELY)


def get_status() -> dict:
    """Return current browser stack status."""
    return {
        "browser_use_version": "0.12.6",
        "playwright_version": "1.59.0",
        "chrome_cdp_active": chrome_cdp_active(),
        "cdp_url": CDP_URL,
        "ollama_model": OLLAMA_MODEL,
        "max_steps": MAX_STEPS,
        "screenshots_dir": str(SCREENSHOTS),
        "known_captcha_sites": CAPTCHA_LIKELY,
        "limitations": [
            "qwen2.5:1.5b struggles with complex multi-step navigation (upgrade to 7b+ for reliability)",
            "Fiverr/Upwork/LinkedIn block with reCAPTCHA",
            "Chrome CDP shared with Flow Director — task queue matters",
        ]
    }

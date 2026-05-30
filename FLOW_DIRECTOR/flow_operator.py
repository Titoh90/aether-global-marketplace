#!/usr/bin/env python3
"""
flow_operator.py — IMPERIO Google Flow Operator (Playwright CDP)
================================================================
Operates Google Flow via Chrome remote debugging port (CDP).
NO AppleScript. NO headless. Real Chrome session with user cookies.

APPROACH (discovered 2026-05-17):
  1. Launch Chrome with --remote-debugging-port=9222 (copies Profile 1)
  2. Connect Playwright via connect_over_cdp('http://localhost:9222')
  3. Find Flow page by URL pattern (labs.google)
  4. Interact: upload image → click Iniciar → type prompt → click Crear
  5. Detect completion via UUID polling (NOT network listener)
  6. Download via pg.request.get() (uses session cookies, no API key)

KEY LESSONS (discovered 2026-05-17 session):
  - JS Apple Events blocked in Chrome Protected Preferences → AppleScript broken
  - Must copy FULL Profile dir (not just cookies) for Keychain auth to work
  - UUID appears in DOM IMMEDIATELY as placeholder — NOT ready yet
  - Poll the UUID URL until body > 500KB (JPEG ~84KB during gen, MP4 ~2MB when done)
  - Network response listener captures CACHED old responses → use DOM UUID diff
  - Picker item: click HEADER ROW at y≈107 (body click doesn't trigger selection)
  - Rights dialog after upload: find button text 'Aceptar' and click
  - Generate button: text 'Crear'/'arrow_forward' at roughly (875, 600)
  - Iniciar slot class: .gjOFny (CSS) — fallback: innerText === 'Iniciar'

CHROME SETUP (one-time per machine):
  cp -r "~/Library/Application Support/Google/Chrome/Profile 1/" /tmp/chrome_dbg_root/Default/
  /Applications/Google Chrome.app/Contents/MacOS/Google Chrome \
    --remote-debugging-port=9222 \
    --user-data-dir=/tmp/chrome_dbg_root \
    --profile-directory=Default \
    --no-first-run --no-default-browser-check \
    https://labs.google/fx/es-419/tools/flow/project/YOUR_PROJECT_ID
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from playwright.async_api import async_playwright, Browser, Page

# ─── CONSTANTS ────────────────────────────────────────────────────────────────

BASE_DIR     = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FLOW_DIRECTOR")
CLIPS_DIR    = BASE_DIR / "clips"
FRAMES_DIR   = BASE_DIR / "frames"
ASSETS_DIR   = BASE_DIR / "assets"
CAROUSEL_DIR = BASE_DIR / "carousel"

CDP_URL          = "http://localhost:9222"
FLOW_BASE        = "https://labs.google/fx/es-419/tools/flow"
FLOW_PROJECT_URL = "https://labs.google/fx/es-419/tools/flow/project/{project_id}"
MEDIA_URL        = "https://labs.google/fx/api/trpc/media.getMediaUrlRedirect?name={uuid}"

# Regex for media UUID extraction from page HTML
UUID_RE = re.compile(
    r'name=([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
)

# Chrome debug profile paths
CHROME_DBG_ROOT  = Path("/tmp/chrome_dbg_root")
CHROME_PROFILE_SRC = Path.home() / "Library/Application Support/Google/Chrome/Profile 1"


# ─── CHROME SETUP ─────────────────────────────────────────────────────────────

def is_chrome_debug_running() -> bool:
    """Check if Chrome CDP is available on port 9222."""
    import urllib.request
    try:
        urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=2)
        return True
    except Exception:
        return False


def setup_chrome_debug_profile(force: bool = False) -> bool:
    """
    Copy Chrome Profile 1 → /tmp/chrome_dbg_root/Default/
    Same Chrome binary → same Keychain key → Google session works without re-login.
    """
    dest = CHROME_DBG_ROOT / "Default"
    if dest.exists() and not force:
        return True
    if not CHROME_PROFILE_SRC.exists():
        print(f"ERROR: Chrome Profile 1 not found: {CHROME_PROFILE_SRC}")
        return False
    print(f"Copying Chrome profile → {dest} ...")
    if dest.exists():
        shutil.rmtree(dest)
    CHROME_DBG_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copytree(str(CHROME_PROFILE_SRC), str(dest))
    print("Profile copied OK")
    return True


def launch_chrome_debug(project_url: str = FLOW_BASE) -> bool:
    """Launch Chrome with remote debugging port 9222."""
    cmd = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "--remote-debugging-port=9222",
        f"--user-data-dir={CHROME_DBG_ROOT}",
        "--profile-directory=Default",
        "--no-first-run", "--no-default-browser-check", "--disable-sync",
        project_url,
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(10):
        if is_chrome_debug_running():
            return True
        time.sleep(1)
    return False


def ensure_chrome_ready(project_url: str = FLOW_BASE) -> bool:
    """Full setup: copy profile → launch Chrome → wait for CDP. Call before connect()."""
    if is_chrome_debug_running():
        return True
    if not setup_chrome_debug_profile():
        return False
    return launch_chrome_debug(project_url)


# ─── FLOW OPERATOR ────────────────────────────────────────────────────────────

class FlowOperator:
    """
    Async operator for Google Flow.

    Async usage:
        op = FlowOperator(plan)
        await op.connect()
        plan = await op.run()
        await op.close()

    Sync usage (from flow_agent.py):
        plan = FlowOperator.run_sync(plan)
    """

    def __init__(self, plan: dict, no_interactive: bool = False):
        self.plan = plan
        self.no_interactive = no_interactive
        self.execution_log: list = []
        self._pw = None
        self._browser: Browser = None
        self._pg: Page = None

    # ── Connection ──────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        if not is_chrome_debug_running():
            self._log("Chrome not on port 9222, launching...")
            ensure_chrome_ready()
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.connect_over_cdp(CDP_URL)
        ctx = self._browser.contexts[0]
        self._pg = next(
            (p for p in ctx.pages if "labs.google" in p.url),
            ctx.pages[0] if ctx.pages else None,
        )
        if not self._pg:
            self._log("ERROR: No pages found in Chrome")
            return False
        # Set viewport to 1920x1080 so generate button is always visible in viewport
        await self._pg.set_viewport_size({"width": 1920, "height": 1080})
        # If on clip-editor URL (/edit/...), navigate to project root first
        current_url = self._pg.url
        if "/edit/" in current_url and "labs.google" in current_url:
            # Strip /edit/... suffix — split on /edit/ and keep left part
            project_root = current_url.split("/edit/")[0]
            self._log(f"On clip-editor URL — navigating to project root: {project_root}")
            await self._pg.goto(project_root, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(4)

        # Ensure we are on the generation UI, not the project content/explore page.
        # The content page (/project/... without /edit/) and explore page (/tools/flow)
        # do not have a prompt input. The correct generation URL is /project/{id}/edit/new.
        current_url = self._pg.url
        needs_gen_ui = (
            ("/project/" in current_url and "/edit/" not in current_url)
            or current_url.rstrip("/") == FLOW_BASE.rstrip("/")
        )
        if needs_gen_ui:
            # Extract project ID from any Flow page, or use the known project ID
            m = re.search(r"/project/([a-f0-9-]+)", current_url)
            if m:
                project_id = m.group(1)
            else:
                # Fallback: use the project ID from the known project URL
                project_id = "31aade33-b4b9-4615-8cd0-b6d912851fb7"
            gen_url = f"{FLOW_BASE}/project/{project_id}/edit/new"
            self._log(f"Navigating to generation UI: {gen_url}")
            await self._pg.goto(gen_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(4)

        self._log(f"Connected: {self._pg.url}")
        return True

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    # ── UUID Helpers ─────────────────────────────────────────────────────────

    async def _get_page_uuids(self) -> set:
        """Extract all media UUIDs from current page HTML."""
        html = await self._pg.evaluate("() => document.documentElement.innerHTML")
        return set(UUID_RE.findall(html))

    async def _wait_for_new_uuid(self, existing: set, timeout: int = 60) -> str:
        """
        Wait for a NEW UUID to appear in DOM (different from existing set).
        UUID appears immediately as placeholder — NOT yet downloadable.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            current = await self._get_page_uuids()
            new = current - existing
            if new:
                uuid = list(new)[-1]
                self._log(f"  New UUID: {uuid}")
                return uuid
            await asyncio.sleep(2)
        return None

    async def _poll_uuid_until_ready(
        self, uuid: str, min_size: int = 500_000,
        interval: int = 12, max_retries: int = 50
    ) -> tuple:
        """
        Poll media URL until body is large enough.
        - During gen: returns JPEG thumbnail ~84KB
        - After gen:  returns MP4 ~2MB+ (video) or PNG ~200KB+ (image)
        Returns (url, body_bytes) or (url, None) on timeout.
        """
        url = MEDIA_URL.format(uuid=uuid)
        for i in range(max_retries):
            try:
                resp = await self._pg.request.get(url, timeout=20000)
                body = await resp.body()
                if len(body) >= min_size:
                    self._log(f"  Ready! {len(body)//1024}KB (attempt {i})")
                    return url, body
                if i % 3 == 0:
                    self._log(f"  [{i}] polling {uuid[:8]}... size={len(body)}B")
            except Exception as e:
                self._log(f"  [{i}] poll error: {e}")
            await asyncio.sleep(interval)
        return url, None

    # ── UI Helpers ───────────────────────────────────────────────────────────

    async def _wait_for_iniciar(self, timeout: int = 45) -> dict:
        """
        Wait for Iniciar (start frame) slot. Returns {x,y,m} or None.
        m='empty' = slot unfilled (shows 'Iniciar' text)
        m='filled' = slot already has image (leftmost cancel button)

        2026-05-29: swap_horiz removed from new UI. Use text + position.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = await self._pg.evaluate("""
            () => {
                const all = Array.from(document.querySelectorAll('*'));
                const btns = Array.from(document.querySelectorAll('button'));

                // Empty slot: text 'Iniciar' (or 'chrome_extension' icon + 'In' truncated)
                const el = all.find(e => {
                    const t = (e.innerText||'').trim();
                    const w = e.getBoundingClientRect().width;
                    return (t === 'Iniciar' || (t.includes('chrome_extension') && t.includes('In')))
                        && w > 0 && w < 200;
                });
                if (el) {
                    const r = el.getBoundingClientRect();
                    return {x: r.x+r.width/2, y: r.y+r.height/2, m: 'empty'};
                }

                // Filled slot: leftmost cancel button in the frame slot area (y 300-800)
                const cancelBtns = btns.filter(b => {
                    const t = (b.innerText||'').trim();
                    const r = b.getBoundingClientRect();
                    return t === 'cancel' && r.width > 0 && r.width < 50 && r.y > 300 && r.y < 800;
                }).sort((a, b) => a.getBoundingClientRect().x - b.getBoundingClientRect().x);

                if (cancelBtns.length >= 1) {
                    const r = cancelBtns[0].getBoundingClientRect();
                    return {x: r.x+r.width/2, y: r.y+r.height/2, m: 'filled'};
                }
                return null;
            }
            """)
            if r:
                self._log(f"  Iniciar ({r['m']}) at ({r['x']:.0f},{r['y']:.0f})")
                return r
            await asyncio.sleep(1)
        return None

    async def _wait_for_fin(self, timeout: int = 30) -> dict:
        """
        Wait for Fin (end frame) slot. Returns {x,y,m} or None.
        m='empty' = slot unfilled, m='filled' = has image (cancel RIGHT of swap).
        Uses swap_horiz button as anchor — position-independent.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = await self._pg.evaluate("""
            () => {
                // Empty slot: text 'Fin'
                const el = Array.from(document.querySelectorAll('*')).find(e =>
                    (e.innerText||e.textContent||'').trim() === 'Fin' &&
                    e.getBoundingClientRect().width > 0 &&
                    e.getBoundingClientRect().width < 100
                );
                if (el) {
                    const r = el.getBoundingClientRect();
                    return {x: r.x+r.width/2, y: r.y+r.height/2, m:'empty'};
                }
                // Filled slot: cancel button RIGHT of swap_horiz button
                const btns = Array.from(document.querySelectorAll('button'));
                const swapBtn = btns.find(b => (b.innerText||'').includes('swap_horiz'));
                if (swapBtn) {
                    const sr = swapBtn.getBoundingClientRect();
                    const sx = sr.x + sr.width/2, sy = sr.y + sr.height/2;
                    const cancelBtn = btns.find(b => {
                        const t = (b.innerText||'').trim();
                        const r = b.getBoundingClientRect();
                        return t === 'cancel' && r.x > sx + 10 &&
                               Math.abs(r.y - sy) < 60 && r.width > 0;
                    });
                    if (cancelBtn) {
                        const r = cancelBtn.getBoundingClientRect();
                        return {x: r.x+r.width/2, y: r.y+r.height/2, m:'filled'};
                    }
                }
                return null;
            }
            """)
            if r:
                self._log(f"  Fin ({r['m']}) at ({r['x']:.0f},{r['y']:.0f})")
                return r
            await asyncio.sleep(1)
        self._log("  WARNING: Fin slot not found")
        return None

    async def _clear_slot(self, slot: str = "start") -> bool:
        """
        Clear a filled frame slot by clicking its cancel button.
        slot: 'start' = Iniciar (LEFT of swap), 'end' = Fin (RIGHT of swap)
        Uses swap_horiz button as anchor — position-independent.
        """
        side = "left" if slot == "start" else "right"
        cleared = await self._pg.evaluate(f"""
        () => {{
            const btns = Array.from(document.querySelectorAll('button'));
            const swapBtn = btns.find(b => (b.innerText||'').includes('swap_horiz'));
            if (!swapBtn) return false;
            const sr = swapBtn.getBoundingClientRect();
            const sx = sr.x + sr.width / 2;
            const sy = sr.y + sr.height / 2;
            const b = btns.find(b => {{
                const t = (b.innerText||'').trim();
                const r = b.getBoundingClientRect();
                const onSide = '{side}' === 'left' ? r.x < sx - 10 : r.x > sx + 10;
                return t === 'cancel' && onSide && Math.abs(r.y - sy) < 60 && r.width > 0;
            }});
            if (!b) return false;
            b.click();
            return true;
        }}
        """)
        if cleared:
            await asyncio.sleep(1)
            self._log(f"  Cleared {'Iniciar' if slot=='start' else 'Fin'} slot")
        return cleared

    async def _upload_and_set_slot(self, image_path: Path, slot: str = "start") -> bool:
        """
        Upload a local image and set it in the Iniciar (start) or Fin (end) frame slot.

        Flow (confirmed 2026-05-19):
          1. Clear slot if already filled (click cancel button)
          2. set_input_files → uploads to gallery (Cargas tab)
          3. Click slot div → picker dialog opens
          4. Click 'Cargas' tab → shows uploaded files
          5. Click first item in content area → dialog auto-closes → slot filled

        slot: 'start' = Iniciar, 'end' = Fin
        """
        label = "Iniciar" if slot == "start" else "Fin"
        self._log(f"  Upload → {label}: {image_path.name} ({image_path.stat().st_size//1024}KB)")

        # 1. Check if slot is filled → clear it first
        slots = await self._check_frame_slots()
        if slot == "start" and slots.get("iniciar_filled"):
            self._log(f"  {label} already filled — clearing...")
            await self._clear_slot("start")
        elif slot == "end" and slots.get("fin_filled"):
            self._log(f"  {label} already filled — clearing...")
            await self._clear_slot("end")

        # 2. Upload via hidden file input
        try:
            await self._pg.locator('input[type="file"]').first.set_input_files(str(image_path))
            await asyncio.sleep(4)  # Give server time to process upload
        except Exception as e:
            self._log(f"  set_input_files error: {e}")
            return False

        # 3. Dismiss any rights dialog
        await self._dismiss_dialog()

        # 4. Find the slot (now should be empty after clear)
        if slot == "start":
            slot_pos = await self._wait_for_iniciar(timeout=15)
        else:
            slot_pos = await self._wait_for_fin(timeout=15)

        if not slot_pos:
            self._log(f"  ERROR: {label} slot not found after upload")
            return False

        # Only open picker if slot is empty
        if slot_pos.get("m") == "filled":
            self._log(f"  {label} slot already shows image — treating as set")
            return True

        # 5. Click slot to open picker dialog
        self._log(f"  Opening {label} picker...")
        await self._pg.mouse.click(slot_pos["x"], slot_pos["y"])
        await asyncio.sleep(3)  # Wait for dialog to fully render

        # 5. Check dialog opened
        dialog_open = await self._pg.evaluate("""
        () => { const d=document.querySelector('[role="dialog"]'); return d ? d.getBoundingClientRect().width > 0 : false; }
        """)
        if not dialog_open:
            self._log(f"  Picker dialog did not open — slot may already be set")
            return True

        # 6. Click Cargas tab INSIDE the dialog (uploaded files)
        # IMPORTANT: search only within [role="dialog"] to avoid sidebar buttons
        cargas = None
        for _attempt in range(3):
            cargas = await self._pg.evaluate("""
            () => {
                const dialog = document.querySelector('[role="dialog"]');
                if (!dialog) return null;
                const btns = Array.from(dialog.querySelectorAll('button'));
                const b = btns.find(b => {
                    const t = (b.innerText||'').trim();
                    return t.includes('Cargas') || t.includes('drive_folder_upload');
                });
                if (!b) return null;
                const r = b.getBoundingClientRect();
                return {x: r.x+r.width/2, y: r.y+r.height/2};
            }""")
            if cargas:
                break
            await asyncio.sleep(1.5)

        if cargas:
            self._log(f"  Clicking Cargas tab at ({cargas['x']:.0f},{cargas['y']:.0f})...")
            await self._pg.mouse.click(cargas["x"], cargas["y"])
            await asyncio.sleep(2)
        else:
            self._log("  WARNING: Cargas tab not found in dialog — proceeding without tab switch")

        # 7. Find and click the uploaded file thumbnail
        # Priority: tabindex=0 item with reasonable thumbnail size (not full-dialog containers)
        fname = image_path.name
        clicked = await self._pg.evaluate(f"""
        () => {{
            const fname = {repr(fname)};
            const d = document.querySelector('[role="dialog"]');
            if (!d) return null;

            // Priority 1: tabindex=0 items in content area — these are actual selectable thumbnails
            // Require width < 600 to exclude full-dialog containers
            const tabItems = Array.from(d.querySelectorAll('[tabindex="0"]')).filter(el => {{
                const r = el.getBoundingClientRect();
                return r.x > 300 && r.width > 50 && r.width < 600 && r.height > 50 && r.y > 300;
            }});
            if (tabItems.length > 0) {{
                // Prefer the one containing our filename
                const byName = tabItems.find(el =>
                    (el.innerText||el.textContent||'').includes(fname));
                const best = byName || tabItems[0];
                const r = best.getBoundingClientRect();
                return {{x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2), by:'tabindex'}};
            }}

            // Priority 2: any element with our filename, not too large
            const all = Array.from(d.querySelectorAll('*'));
            const byName = all.find(el => {{
                const t = (el.innerText || el.textContent || '').trim();
                const r = el.getBoundingClientRect();
                return t.includes(fname) && r.x > 300 && r.width > 50 && r.width < 400 && r.height > 30;
            }});
            if (byName) {{
                const r = byName.getBoundingClientRect();
                return {{x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2), by:'name'}};
            }}

            return null;
        }}""")

        if clicked:
            self._log(f"  Clicking item ({clicked['by']}) at ({clicked['x']},{clicked['y']})...")
            await self._pg.mouse.click(clicked["x"], clicked["y"])
            await asyncio.sleep(2)
        else:
            self._log("  WARNING: no item found in picker")

        # 7b. If dialog still open, try clicking "Agregar a la instrucción" button to confirm
        still_open = await self._pg.evaluate("""
        () => { const d=document.querySelector('[role="dialog"]'); return d ? d.getBoundingClientRect().width > 0 : false; }
        """)
        if still_open:
            agregar = await self._pg.evaluate("""
            () => {
                const d = document.querySelector('[role="dialog"]');
                if (!d) return null;
                const b = Array.from(d.querySelectorAll('button')).find(b =>
                    (b.innerText||'').toLowerCase().includes('agregar') ||
                    (b.innerText||'').toLowerCase().includes('add') ||
                    (b.innerText||'').toLowerCase().includes('select'));
                if (!b) return null;
                const r = b.getBoundingClientRect();
                return {x: r.x+r.width/2|0, y: r.y+r.height/2|0, text:(b.innerText||'').trim().slice(0,30)};
            }""")
            if agregar:
                self._log(f"  Clicking confirm button '{agregar['text']}' at ({agregar['x']},{agregar['y']})...")
                await self._pg.mouse.click(agregar["x"], agregar["y"])
                await asyncio.sleep(2)

        # 8. Close dialog if still open
        still_open = await self._pg.evaluate("""
        () => { const d=document.querySelector('[role="dialog"]'); return d ? d.getBoundingClientRect().width > 0 : false; }
        """)
        if still_open:
            self._log(f"  Dialog still open — trying Escape")
            await self._pg.keyboard.press("Escape")
            await asyncio.sleep(1)

        # 9. Verify slot is actually filled (not a false positive)
        final_slots = await self._check_frame_slots()
        is_filled = final_slots.get("iniciar_filled") if slot == "start" else final_slots.get("fin_filled")
        if is_filled:
            self._log(f"  ✓ {label} slot confirmed filled")
            return True
        else:
            self._log(f"  ERROR: {label} slot still empty after picker interaction")
            return False

    async def _find_generate_btn(self) -> dict:
        """
        Find the generate button. Returns {x, y} for mouse.click() or None.
        NOTE: In many Flow UI states, the real button ('Submit (enter)') is outside
        the viewport. When this returns None, _click_generate() uses JS element.click().
        """
        return await self._pg.evaluate("""
        () => {
            const btns = Array.from(document.querySelectorAll('button,[role="button"]'));
            const vw = window.innerWidth, vh = window.innerHeight;

            // Priority 1: 'arrow_forward Crear' — the visible generate button in image mode
            for (const b of btns) {
                const t = (b.innerText||b.textContent||'').trim();
                const r = b.getBoundingClientRect();
                // Must be fully visible in viewport
                if (r.width > 5 && r.top >= 0 && r.bottom <= vh && r.left >= 0 && r.right <= vw
                    && t.includes('arrow_forward') && t.includes('Crear'))
                    return {x:r.x+r.width/2, y:r.y+r.height/2, label:'arrow_forward+Crear'};
            }
            // Priority 2: 'arrow_forward' visible in viewport, not a card action
            for (const b of btns) {
                const t = (b.innerText||b.textContent||'').trim();
                const r = b.getBoundingClientRect();
                if (r.width > 5 && r.top >= 0 && r.bottom <= vh && r.left >= 0 && r.right <= vw
                    && t.includes('arrow_forward') && !t.includes('No se pudo') && !t.includes('Estás'))
                    return {x:r.x+r.width/2, y:r.y+r.height/2, label:'arrow_forward'};
            }
            // Priority 3: 'Crear' visible in viewport, not gallery card/add button
            for (const b of btns) {
                const t = (b.innerText||b.textContent||'').trim();
                const r = b.getBoundingClientRect();
                if (r.width > 5 && r.top >= 0 && r.bottom <= vh && r.left >= 0 && r.right <= vw
                    && t.includes('Crear') && !t.includes('add_2') && !t.startsWith('add'))
                    return {x:r.x+r.width/2, y:r.y+r.height/2, label:'Crear-visible'};
            }
            // If nothing found in viewport, return null → JS click fallback handles it
            return null;
        }
        """)

    async def _find_prompt_input(self) -> dict:
        return await self._pg.evaluate("""
        () => {
            for (const el of document.querySelectorAll('[contenteditable="true"]')) {
                const r = el.getBoundingClientRect();
                if (r.width > 200 && r.y > 400) return {x:r.x+r.width/2, y:r.y+r.height/2};
            }
            return null;
        }
        """)

    async def _dismiss_dialog(self):
        """Click Aceptar/Accept dialog if present (rights confirmation after upload)."""
        r = await self._pg.evaluate("""
        () => {
            for (const b of document.querySelectorAll('button,[role="button"]')) {
                const t = (b.innerText||'').trim();
                const r = b.getBoundingClientRect();
                if (r.width > 0 && (t==='Aceptar'||t==='Accept'||t==='OK'))
                    return {x:r.x+r.width/2, y:r.y+r.height/2, t};
            }
            return null;
        }
        """)
        if r:
            self._log(f"  Dismiss dialog: '{r['t']}'")
            await self._pg.mouse.click(r["x"], r["y"])
            await asyncio.sleep(1)

    async def _upload_image(self, path: Path) -> bool:
        """Upload image via hidden file input."""
        self._log(f"  Upload: {path.name} ({path.stat().st_size//1024}KB)")
        try:
            await self._pg.locator('input[type="file"]').first.set_input_files(str(path))
            await asyncio.sleep(2.5)
            return True
        except Exception as e:
            self._log(f"  Upload error: {e}")
            return False

    def _inject_style_bias(self, prompt: str, product_id: str = "") -> str:
        """
        Optionally inject visual style direction into a Flow prompt.
        
        Controlled by FEATURE_STYLE_ROTATION env flag (default: disabled).
        When enabled, appends advisory style hints from ProactiveBrain without
        replacing or mutating the original prompt intent.
        
        Returns the prompt unchanged if flag disabled or no bias available.
        """
        if os.environ.get("FEATURE_STYLE_ROTATION", "0") != "1":
            return prompt
        
        pid = product_id or self.plan.get("asin", "")
        if not pid:
            return prompt
        
        try:
            from core.creative_intelligence.proactive_brain import ProactiveBrain
            brain = ProactiveBrain()
            bias = brain.get_flow_director_style_bias(pid)
            if not bias:
                return prompt
            
            style = bias.get("recommended_style", "")
            if not style:
                return prompt
            
            # Append as soft visual direction (preserves original prompt intent)
            style_hint = (
                f". Visual style: {style.replace('_', ' ').title()}"
                f" ({bias.get('fatigue_level', 'advisory')} rotation)"
            )
            enhanced = prompt + style_hint
            self._log(f"  Style bias injected: {style} (flag=on, product={pid})")
            return enhanced
        except Exception as e:
            self._log(f"  Style bias unavailable: {e}")
            return prompt

    async def _type_prompt(self, text: str) -> bool:
        """
        Type prompt into Flow's contenteditable input.
        Uses element_handle.fill() which properly handles React/ProseMirror
        contenteditables (keyboard.type() alone doesn't trigger input events).
        """
        # Find the contenteditable element handle (not just coordinates)
        handles = await self._pg.query_selector_all('[contenteditable="true"]')
        target = None
        for h in handles:
            box = await h.bounding_box()
            if box and box["width"] > 200 and box["y"] > 400:
                target = h
                break
        if not target:
            self._log("  ERROR: prompt input not found")
            return False

        # fill() on contenteditable: focuses, selects all, and types with proper input events
        await target.fill(text)
        self._log(f"  Typed prompt ({len(text)} chars)")
        await asyncio.sleep(0.8)  # Let Submit button appear after typing
        return True

    async def _is_rate_limited(self) -> bool:
        """Check if Flow is showing a rate limit error."""
        result = await self._pg.evaluate("""
        () => {
            const body = document.body.innerText || '';
            return body.includes('demasiado rápido') ||
                   body.includes('too many requests') ||
                   body.includes('too quickly') ||
                   body.includes('Aguarda un momento');
        }
        """)
        return bool(result)

    async def _click_generate(self):
        """Click the generate/Crear button using multiple strategies."""
        # Strategy 1: DOM button detection (handles image mode ~(870,600))
        btn = await self._find_generate_btn()
        if btn:
            self._log(f"  Generate at ({btn['x']:.0f},{btn['y']:.0f})")
            await self._pg.mouse.click(btn["x"], btn["y"])
            return

        # Strategy 2: JS element.click() on form submit — works even outside viewport
        clicked = await self._pg.evaluate("""
        () => {
            // Try input[type=submit]
            const submit = document.querySelector('input[type="submit"]');
            if (submit && !submit.disabled) { submit.click(); return 'input[submit]'; }
            // Try button[type=submit]
            const bsubmit = document.querySelector('button[type="submit"]');
            if (bsubmit && !bsubmit.disabled) { bsubmit.click(); return 'button[submit]'; }
            // Try ALL elements (including off-viewport) with 'Crear' in text
            const allEls = Array.from(document.querySelectorAll('button,[role="button"],input'));
            for (const b of allEls) {
                const t = (b.innerText||b.textContent||b.value||'').trim();
                if ((t.includes('Crear') || t.includes('Submit') || t.includes('Generate'))
                    && !t.includes('add_2') && !t.includes('add ')) {
                    b.click(); return 'found: ' + t.slice(0,30);
                }
            }
            // Dispatch Ctrl+Enter on the contenteditable prompt
            const prompt = document.querySelector('[contenteditable="true"]');
            if (prompt) {
                prompt.focus();
                prompt.dispatchEvent(new KeyboardEvent('keydown', {
                    key: 'Enter', code: 'Enter', ctrlKey: true, bubbles: true, cancelable: true
                }));
                prompt.dispatchEvent(new KeyboardEvent('keyup', {
                    key: 'Enter', code: 'Enter', ctrlKey: true, bubbles: true
                }));
                return 'ctrl+enter-dispatched';
            }
            return null;
        }
        """)
        if clicked:
            self._log(f"  Generate via JS: {clicked}")
            # Reinforce with keyboard Enter on prompt — Flow sometimes needs this
            await asyncio.sleep(0.5)
            prompt_el = await self._pg.evaluate(
                "() => !!document.querySelector('[contenteditable=\"true\"]')")
            if prompt_el:
                await self._pg.keyboard.press("Enter")
                self._log("  Reinforced with Enter key")
        else:
            self._log("  Generate: all strategies failed")

        # Strategy 3 (final fallback): scroll page to bottom to reveal Crear button,
        # then retry DOM detection and click at known coordinates if found.
        # This handles long prompts that push the button out of viewport.
        await asyncio.sleep(1.0)
        await self._pg.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(0.5)
        btn2 = await self._find_generate_btn()
        if btn2:
            self._log(f"  [fallback] Generate after scroll at ({btn2['x']:.0f},{btn2['y']:.0f})")
            await self._pg.mouse.click(btn2["x"], btn2["y"])
            return
        # Last resort: click at known working coordinates for 1920x1080 viewport
        self._log("  [fallback] Clicking known coordinate (1236, 1023)")
        await self._pg.mouse.click(1236, 1023)

    async def _find_model_btn(self) -> dict:
        """Find the model selector chip in the bottom bar.

        2026-05-29: Flow redesigned to chat-style editor. Model chip is now a
        button containing model name (e.g. '🍌 Nano Banana 2 crop_16_9 x2')
        in the bottom input bar. We search by text content first (reliable),
        then fall back to positional heuristics.
        """
        return await self._pg.evaluate("""
        () => {
            const MODEL_KW = ['nano banana', 'veo', 'imagen 4', 'omni flash'];
            const CHIP_KW  = ['crop_', 'x2', 'x3', 'x4', 'video'];
            const btns = Array.from(document.querySelectorAll('button,[role="button"]'));

            // Pass 1: find by model name keywords (most reliable)
            for (const b of btns) {
                const r = b.getBoundingClientRect();
                if (r.width < 30 || r.height < 10 || r.width > 500) continue;
                const t = (b.innerText||b.textContent||'').trim().toLowerCase();
                if (MODEL_KW.some(k => t.includes(k))) {
                    return {x: r.x + r.width/2, y: r.y + r.height/2, t};
                }
            }

            // Pass 2: find by chip indicators (crop icon + count suffix)
            for (const b of btns) {
                const r = b.getBoundingClientRect();
                if (r.width < 30 || r.height < 10 || r.width > 500) continue;
                const t = (b.innerText||b.textContent||'').trim().toLowerCase();
                if (CHIP_KW.filter(k => t.includes(k)).length >= 2) {
                    return {x: r.x + r.width/2, y: r.y + r.height/2, t};
                }
            }

            // Pass 3: positional fallback — bottom 100px of viewport
            const vh = window.innerHeight;
            for (const b of btns) {
                const r = b.getBoundingClientRect();
                const cy = r.y + r.height / 2;
                if (cy > vh - 100 && r.width > 60 && r.width < 400 && r.height < 60) {
                    const t = (b.innerText||'').trim().toLowerCase();
                    if (t.includes('crop') || t.includes('video') || t.includes('image')) {
                        return {x: r.x + r.width/2, y: r.y + r.height/2, t};
                    }
                }
            }
            return null;
        }
        """)

    async def _switch_mode(self, mode: str = "Image") -> bool:
        """
        Switch between Video and Image generation modes.
        mode: 'Image' (Nano Banana, FREE) or 'Video' (Veo 3.1, uses credits)
        For Video with start+end frames, use _ensure_video_frames_mode() instead.
        """
        IMAGE_KEYWORDS = ['nano banana', 'imagen', 'image', '🍌']
        VIDEO_KEYWORDS = ['veo', 'video']
        # "nano banana 2" is a video model despite matching IMAGE_KEYWORDS — exclude explicitly
        VIDEO_MODEL_EXCEPTIONS = ['nano banana 2']

        model_btn = await self._find_model_btn()
        if not model_btn:
            self._log(f"  WARNING: Could not find model selector button")
            return False

        current_text = model_btn.get("t", "")
        desired_lower = mode.lower()

        _is_image_model = (
            any(k in current_text for k in IMAGE_KEYWORDS) and
            not any(v in current_text for v in VIDEO_MODEL_EXCEPTIONS)
        )
        if desired_lower == "image" and _is_image_model:
            self._log(f"  Already in Image mode ({current_text[:30]})")
            return True
        if desired_lower == "video" and any(k in current_text for k in VIDEO_KEYWORDS):
            # Must also verify we're NOT in Fotogramas mode (which also shows "video" in btn text)
            # Fotogramas mode has a visible Fin slot; plain Video mode does not
            slots = await self._check_frame_slots()
            if not slots.get("has_fin"):
                self._log(f"  Already in Video mode ({current_text[:30]})")
                return True
            # has_fin = True → stuck in Fotogramas mode — fall through to switch out
            self._log(f"  Detected Fotogramas mode — switching to plain Video...")

        await self._pg.mouse.click(model_btn["x"], model_btn["y"])
        await asyncio.sleep(1.5)

        # Click the desired tab in the popup
        tab_keywords = IMAGE_KEYWORDS if mode.lower() == "image" else VIDEO_KEYWORDS
        # Include Spanish UI keywords (Flow es-419 uses "Imagen"/"Video")
        if mode.lower() == "image":
            tab_keywords = tab_keywords + ['imagen', 'imag', 'nano banana', '🍌']
        # Use [role="tab"] selector — the popup uses tabs not buttons
        opt = await self._pg.evaluate(f"""
        () => {{
            const keywords = {tab_keywords};
            const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
            for (const b of tabs) {{
                const t = (b.innerText||b.textContent||'').trim().toLowerCase();
                const r = b.getBoundingClientRect();
                if (r.width > 0 && r.height > 0 && keywords.some(k => t.includes(k))) {{
                    return {{x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2), t}};
                }}
            }}
            return null;
        }}
        """)
        if opt:
            await self._pg.mouse.click(opt["x"], opt["y"])
            await asyncio.sleep(1.5)
            # Close picker with Escape (does NOT revert selection, unlike clicking btn again)
            await self._pg.keyboard.press("Escape")
            await asyncio.sleep(0.8)
            # Verify the switch actually worked
            model_btn2 = await self._find_model_btn()
            new_text = model_btn2.get("t", "") if model_btn2 else ""
            if desired_lower == "image" and any(k in new_text for k in IMAGE_KEYWORDS):
                self._log(f"  Switched to {mode} mode ✓ ({new_text[:30]})")
                return True
            elif desired_lower == "video" and any(k in new_text for k in VIDEO_KEYWORDS):
                self._log(f"  Switched to {mode} mode ✓ ({new_text[:30]})")
                return True
            # Switch didn't stick — try once more without the close click
            self._log(f"  Retry switch to {mode} (current: {new_text[:30]})")
            if model_btn2:
                await self._pg.mouse.click(model_btn2["x"], model_btn2["y"])
                await asyncio.sleep(1.5)
                opt2 = await self._pg.evaluate(f"""
                () => {{
                    const keywords = {tab_keywords};
                    const btns = Array.from(document.querySelectorAll('button'));
                    for (const b of btns) {{
                        const t = (b.innerText||'').trim().toLowerCase();
                        const r = b.getBoundingClientRect();
                        if (r.width > 0 && r.width < 200 && keywords.some(k => t.includes(k))) {{
                            const modelBtns = btns.filter(mb => mb.getAttribute('aria-haspopup') === 'menu');
                            if (modelBtns.every(mb => mb !== b)) return {{x:r.x+r.width/2, y:r.y+r.height/2, t}};
                        }}
                    }}
                    return null;
                }}
                """)
                if opt2:
                    await self._pg.mouse.click(opt2["x"], opt2["y"])
                    await asyncio.sleep(1.5)
                    await self._pg.keyboard.press("Escape")
                    await asyncio.sleep(0.8)
            self._log(f"  Switched to {mode} mode (was: {current_text[:30]})")
            return True

        # Close picker with Escape
        await self._pg.keyboard.press("Escape")
        await asyncio.sleep(0.5)
        self._log(f"  WARNING: Could not switch to {mode} mode (current: {current_text[:30]})")
        return False

    async def _ensure_video_frames_mode(self, aspect_ratio: str = "9:16") -> bool:
        """
        Switch to Veo 3.1 + Fotogramas (start+end frame) mode.
        Sequence: model picker → Video tab → Fotogramas tab → aspect ratio → Escape.
        Returns True when Iniciar AND Fin slots are both visible.

        UI confirmed 2026-05-19:
          Video tab:     y≈348, text contains 'Video'+'play_circle'
          Fotogramas tab: y≈386, text contains 'Fotogramas'
          Aspect ratio btns: y≈424, text contains icon name (crop_9_16, crop_16_9, ...)
          After Escape: Iniciar slot at (315,426), Fin slot at (405,426)
        """
        # NOTE: We do NOT short-circuit here even if slots are visible.
        # Visible Iniciar/Fin slots may belong to an existing clip editor (not a fresh
        # generation form). Without going through the mode-picker we end up without a
        # Crear button. Always open the picker to get a clean generation form.

        model_btn = await self._find_model_btn()
        if not model_btn:
            self._log("  ERROR: Model selector button not found")
            return False

        self._log(f"  Opening model picker (current: {model_btn.get('t','')[:25]})...")
        await self._pg.mouse.click(model_btn["x"], model_btn["y"])
        await asyncio.sleep(1.5)

        # Click Video tab — search by icon+text, not y position (works any viewport height)
        video_tab = await self._pg.evaluate("""
        () => {
            const btns = Array.from(document.querySelectorAll('button'));
            // Video tab has 'play_circle' icon + 'Video' — NOT 'Ver videos' sidebar button
            const b = btns.find(b => {
                const t = (b.innerText||'').trim();
                const r = b.getBoundingClientRect();
                return t.includes('Video') && t.includes('play_circle')
                       && r.width > 20 && r.width < 200 && r.x > 100;
            })
            // Fallback: any Video button in picker area (x > 100 to skip sidebar)
            || btns.find(b => {
                const t = (b.innerText||'').trim();
                const r = b.getBoundingClientRect();
                return t.toLowerCase().includes('video') && r.width > 20 && r.width < 200 && r.x > 100
                       && !t.includes('Ver videos') && !t.includes('videocam');
            });
            if (!b) return null;
            const r = b.getBoundingClientRect();
            return {x: r.x+r.width/2, y: r.y+r.height/2, t: (b.innerText||'').trim().slice(0,30)};
        }""")
        if video_tab:
            self._log(f"  Clicking Video tab ({video_tab.get('t','')[:20]})...")
            await self._pg.mouse.click(video_tab["x"], video_tab["y"])
            await asyncio.sleep(1)
        else:
            self._log("  WARNING: Video tab not found in picker")

        # Click Fotogramas tab — search by text only (no y constraint)
        frames_tab = await self._pg.evaluate("""
        () => {
            const btns = Array.from(document.querySelectorAll('button'));
            const b = btns.find(b => {
                const t = (b.innerText||'').trim();
                const r = b.getBoundingClientRect();
                return (t.includes('Fotogramas') || t.includes('crop_free'))
                       && r.width > 20 && r.width < 200 && r.x > 100;
            });
            if (!b) return null;
            const r = b.getBoundingClientRect();
            return {x: r.x+r.width/2, y: r.y+r.height/2};
        }""")
        if frames_tab:
            self._log("  Clicking Fotogramas tab...")
            await self._pg.mouse.click(frames_tab["x"], frames_tab["y"])
            await asyncio.sleep(1)
        else:
            self._log("  WARNING: Fotogramas tab not found")

        # Set aspect ratio
        ICON_MAP = {"9:16": "crop_9_16", "16:9": "crop_16_9", "1:1": "crop_square", "3:4": "crop_portrait"}
        target_icon = ICON_MAP.get(aspect_ratio, "crop_9_16")
        ar_btn = await self._pg.evaluate(f"""
        () => {{
            const icon = '{target_icon}';
            const btns = Array.from(document.querySelectorAll('button'));
            const b = btns.find(b => {{
                const t = (b.innerText||'').trim();
                const r = b.getBoundingClientRect();
                return (t.includes(icon)) && r.width > 20 && r.width < 200;
            }});
            if (!b) return null;
            const r = b.getBoundingClientRect();
            return {{x: r.x+r.width/2, y: r.y+r.height/2}};
        }}""")
        if ar_btn:
            self._log(f"  Setting aspect ratio {aspect_ratio}...")
            await self._pg.mouse.click(ar_btn["x"], ar_btn["y"])
            await asyncio.sleep(0.5)
        else:
            self._log(f"  WARNING: aspect ratio {aspect_ratio} btn not found")

        # Close picker by clicking the model button again (commits selection)
        # NOTE: Escape reverts the selection — don't use it!
        model_btn2 = await self._find_model_btn()
        if model_btn2:
            await self._pg.mouse.click(model_btn2["x"], model_btn2["y"])
            await asyncio.sleep(0.5)
        await asyncio.sleep(0.8)

        # Verify
        slots = await self._check_frame_slots()
        if slots.get("has_iniciar") and slots.get("has_fin"):
            self._log("  ✓ Video+Fotogramas mode active (Iniciar + Fin slots visible)")
            return True
        elif slots.get("has_iniciar"):
            self._log("  Partial: Iniciar visible but Fin not found (single-frame mode)")
            return True
        else:
            self._log(f"  WARNING: frame slots not confirmed after setup: {slots}")
            # Still return True if model shows video mode — slots may appear after prompt click
            model_btn3 = await self._find_model_btn()
            if model_btn3 and "video" in model_btn3.get("t", ""):
                self._log("  Video mode confirmed via model button — continuing")
                return True
            return False

    async def _check_frame_slots(self) -> dict:
        """
        Return presence of Iniciar and Fin slots (empty OR filled).

        Empty  slot: shows text 'Iniciar' or 'Fin'
        Filled slot: shows 'cancel' buttons — Iniciar = leftmost, Fin = rightmost

        2026-05-29: swap_horiz removed from new UI. Use position-based detection.
        """
        return await self._pg.evaluate("""
        () => {
            const all = Array.from(document.querySelectorAll('*'));
            const btns = Array.from(document.querySelectorAll('button'));

            // Empty slots
            const hasIniciarEmpty = all.some(e =>
                (e.innerText||e.textContent||'').trim() === 'Iniciar' &&
                e.getBoundingClientRect().width > 0);
            const hasFinEmpty = all.some(e =>
                (e.innerText||e.textContent||'').trim() === 'Fin' &&
                e.getBoundingClientRect().width > 0 &&
                e.getBoundingClientRect().width < 100);

            // Filled slots — find cancel buttons in panel area (y 300-800), sort by x
            const cancelBtns = btns.filter(b => {
                const t = (b.innerText||'').trim();
                const r = b.getBoundingClientRect();
                return t === 'cancel' && r.width > 0 && r.width < 50 && r.y > 300 && r.y < 800;
            }).sort((a, b) => a.getBoundingClientRect().x - b.getBoundingClientRect().x);

            // Only count as frame slots if 2+ cancel buttons share same row (y within 60px)
            // or fall back to length-based heuristic (leftmost=Iniciar, rightmost=Fin)
            let hasIniciarFilled = false;
            let hasFinFilled = false;
            if (cancelBtns.length >= 2) {
                const r0 = cancelBtns[0].getBoundingClientRect();
                const rN = cancelBtns[cancelBtns.length - 1].getBoundingClientRect();
                if (Math.abs(r0.y - rN.y) < 60) {
                    hasIniciarFilled = true;
                    hasFinFilled = true;
                }
            } else if (cancelBtns.length === 1) {
                // Single cancel button — assume Iniciar filled (Fin may not exist)
                hasIniciarFilled = true;
            }

            return {
                has_iniciar: hasIniciarEmpty || hasIniciarFilled,
                has_fin: hasFinEmpty || hasFinFilled,
                iniciar_filled: hasIniciarFilled,
                fin_filled: hasFinFilled,
                iniciar_empty: hasIniciarEmpty,
                fin_empty: hasFinEmpty,
            };
        }
        """)

    # ── Frame Extraction ─────────────────────────────────────────────────────

    def _extract_last_frame(self, video: Path, frame: Path) -> bool:
        """FFmpeg: extract last frame at (duration - 0.1s) for continuity."""
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_format", str(video)],
                capture_output=True, text=True
            )
            dur = float(json.loads(r.stdout)["format"]["duration"])
            ts = max(0, dur - 0.1)
            FRAMES_DIR.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(video),
                 "-ss", str(ts), "-frames:v", "1", "-update", "1", str(frame)],
                capture_output=True
            )
            ok = frame.exists() and frame.stat().st_size > 10000
            self._log(f"  Frame: {frame.name} ({frame.stat().st_size//1024}KB)" if ok
                      else "  Frame extraction FAILED")
            return ok
        except Exception as e:
            self._log(f"  Frame error: {e}")
            return False

    # ── Aspect Ratio ─────────────────────────────────────────────────────────

    async def _set_aspect_ratio(self, ratio: str = "9:16") -> bool:
        """
        Set aspect ratio in the model config panel.
        ratio: '9:16' (portrait/TikTok), '16:9' (landscape), '1:1' (square)

        The model selector button (bottom bar) shows current ratio as a material icon:
          crop_9_16 = 9:16 portrait
          crop_16_9 = 16:9 landscape
          crop_square = 1:1

        When clicked, opens a panel with aspect ratio options.
        """
        # Map ratio string to material icon name (used to detect current state)
        ICON_MAP = {"9:16": "crop_9_16", "16:9": "crop_16_9", "1:1": "crop_square"}
        target_icon = ICON_MAP.get(ratio, "crop_9_16")

        model_btn = await self._find_model_btn()
        if not model_btn:
            self._log(f"  WARNING: aspect ratio panel not found (model btn missing)")
            return False

        if target_icon in model_btn.get("t", ""):
            self._log(f"  Aspect ratio already {ratio}")
            return True

        await self._pg.mouse.click(model_btn["x"], model_btn["y"])
        await asyncio.sleep(1.5)

        # Find and click the target aspect ratio option
        # New UI (2026-05-29): panel shows ratio buttons as "16:9", "4:3", "1:1", "3:4", "9:16"
        # Also still check material icon names as fallback
        clicked = await self._pg.evaluate(f"""
        () => {{
            const target = '{target_icon}';
            const ratio_text = '{ratio}';
            const els = Array.from(document.querySelectorAll('button, [role="menuitem"], [role="option"], [role="tab"], li'));
            // Pass 1: exact ratio text match (new UI)
            for (const el of els) {{
                const t = (el.innerText||el.textContent||'').trim();
                const r = el.getBoundingClientRect();
                if (r.width > 10 && r.width < 300 && r.height > 0 && t === ratio_text) {{
                    el.click();
                    return {{x:r.x+r.width/2, y:r.y+r.height/2, t: t.toLowerCase()}};
                }}
            }}
            // Pass 2: material icon name fallback (old UI)
            for (const el of els) {{
                const t = (el.innerText||el.textContent||'').trim().toLowerCase();
                const r = el.getBoundingClientRect();
                if (r.width > 20 && r.width < 300 && r.height > 0 && t.includes(target)) {{
                    el.click();
                    return {{x:r.x+r.width/2, y:r.y+r.height/2, t}};
                }}
            }}
            return null;
        }}
        """)

        if clicked:
            self._log(f"  Set aspect ratio → {ratio}")
            await asyncio.sleep(0.8)
            # Close the config panel so prompt input is accessible
            await self._pg.keyboard.press("Escape")
            await asyncio.sleep(0.5)
            return True

        # Close panel even on failure
        await self._pg.keyboard.press("Escape")
        await asyncio.sleep(0.3)
        self._log(f"  WARNING: could not set aspect ratio {ratio}")
        return False

    async def _set_count(self, count: int = 2) -> bool:
        """
        Set image generation count (x1, x2, x3, x4) in the model config panel.
        Panel must already be open (called from generate_images after _set_aspect_ratio).

        2026-05-29: New UI shows count as buttons labeled "1x", "x2", "x3", "x4".
        """
        if count < 1 or count > 4:
            count = 2
        # Open config panel
        model_btn = await self._find_model_btn()
        if not model_btn:
            self._log(f"  WARNING: count panel not found (model btn missing)")
            return False

        # Check if already set (chip text contains e.g. "x2")
        chip_text = model_btn.get("t", "")
        count_str = f"x{count}"
        if count == 1:
            count_str = "1x"
        if count_str in chip_text:
            self._log(f"  Count already {count}")
            return True

        await self._pg.mouse.click(model_btn["x"], model_btn["y"])
        await asyncio.sleep(1.2)

        # Find and click count button
        clicked = await self._pg.evaluate(f"""
        () => {{
            const target = {count};
            const labels = ['1x', 'x2', 'x3', 'x4'];
            const wanted = target === 1 ? '1x' : 'x' + target;
            const els = document.querySelectorAll('button, [role="option"], [role="radio"]');
            for (const el of els) {{
                const t = (el.innerText||el.textContent||'').trim().toLowerCase();
                const r = el.getBoundingClientRect();
                if (r.width > 10 && r.width < 200 && r.height > 0 && t === wanted) {{
                    el.click();
                    return {{x: r.x+r.width/2, y: r.y+r.height/2, t}};
                }}
            }}
            return null;
        }}
        """)

        if clicked:
            self._log(f"  Set count → {count}")
            await asyncio.sleep(0.5)
            await self._pg.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            return True

        await self._pg.keyboard.press("Escape")
        await asyncio.sleep(0.3)
        self._log(f"  WARNING: could not set count {count}")
        return False

    # ── Animate Image → Video (FREE) ────────────────────────────────────────

    async def animate_image(
        self,
        image_uuid: str = None,
        image_index: int = None,
        out_path: Path = None,
    ) -> Path:
        """
        Convert a generated image to video using Flow's "Animar" feature (FREE).
        Hover over gallery thumbnail → click ⋮ menu → click "Animar".

        Either image_uuid or image_index (0-based, from most recent) must be given.
        Waits for video UUID to appear and polls until ready.
        Returns path to saved MP4, or None on failure.
        """
        CLIPS_DIR.mkdir(parents=True, exist_ok=True)

        self._log(f"\n[ANIMATE] uuid={image_uuid} index={image_index}")

        # Find the gallery item to animate
        found = await self._pg.evaluate(f"""
        () => {{
            // Gallery items are typically img elements or div with background-image
            // inside clickable containers. We look for items with UUID in src/href.
            const uuid = '{image_uuid or ""}';
            const idx = {image_index if image_index is not None else -1};
            const items = Array.from(document.querySelectorAll(
                '[data-media-id], .gallery-item, [class*="media"] img, [class*="gallery"] img'
            ));

            // Try by UUID first
            if (uuid) {{
                for (const el of items) {{
                    const src = el.src || el.getAttribute('data-media-id') || '';
                    if (src.includes(uuid)) {{
                        const r = el.getBoundingClientRect();
                        return {{x: r.x + r.width/2, y: r.y + r.height/2}};
                    }}
                }}
            }}

            // Fallback: look for all visible thumbnails and pick by index
            const thumbs = Array.from(document.querySelectorAll('img'))
                .filter(i => {{
                    const r = i.getBoundingClientRect();
                    return r.width > 80 && r.width < 500 && r.height > 80 && r.y > 0;
                }})
                .sort((a,b) => {{
                    const ra = a.getBoundingClientRect();
                    const rb = b.getBoundingClientRect();
                    return rb.y === ra.y ? ra.x - rb.x : rb.y - ra.y;  // newest first
                }});

            if (idx >= 0 && idx < thumbs.length) {{
                const r = thumbs[idx].getBoundingClientRect();
                return {{x: r.x + r.width/2, y: r.y + r.height/2}};
            }}
            // Default: most recent thumbnail
            if (thumbs.length > 0) {{
                const r = thumbs[0].getBoundingClientRect();
                return {{x: r.x + r.width/2, y: r.y + r.height/2}};
            }}
            return null;
        }}
        """)

        if not found:
            self._log("  ERROR: could not find gallery item to animate")
            return None

        # Hover to reveal action buttons
        await self._pg.mouse.move(found["x"], found["y"])
        await asyncio.sleep(1.0)

        # Click ⋮ menu button (appears on hover)
        menu_btn = await self._pg.evaluate("""
        () => {
            // Look for the three-dot menu button near the hovered item
            const btns = Array.from(document.querySelectorAll('button, [role="button"]'));
            for (const b of btns) {
                const t = (b.innerText||b.textContent||b.getAttribute('aria-label')||'').trim().toLowerCase();
                const r = b.getBoundingClientRect();
                if (r.width > 0 && r.width < 60 && r.height > 0 && r.height < 60 &&
                    (t.includes('more') || t.includes('más') || t.includes('⋮') ||
                     t === 'more_vert' || t.includes('opciones') || t.includes('menu'))) {
                    return {x: r.x + r.width/2, y: r.y + r.height/2, t};
                }
            }
            return null;
        }
        """)

        if not menu_btn:
            self._log("  WARNING: ⋮ menu not found — trying direct right-click")
            await self._pg.mouse.click(found["x"], found["y"], button="right")
            await asyncio.sleep(1.0)
        else:
            await self._pg.mouse.click(menu_btn["x"], menu_btn["y"])
            await asyncio.sleep(1.0)

        # Click "Animar" in context menu
        animar = await self._pg.evaluate("""
        () => {
            const items = Array.from(document.querySelectorAll(
                '[role="menuitem"], [role="option"], li, button'
            ));
            for (const el of items) {
                const t = (el.innerText||el.textContent||'').trim().toLowerCase();
                const r = el.getBoundingClientRect();
                if (r.width > 40 && r.height > 0 && (t.includes('animar') || t.includes('animate'))) {
                    return {x: r.x + r.width/2, y: r.y + r.height/2, t};
                }
            }
            return null;
        }
        """)

        if not animar:
            self._log("  ERROR: 'Animar' option not found in menu")
            await self._pg.keyboard.press("Escape")
            return None

        # Collect pre-animation UUIDs
        existing = await self._get_page_uuids()

        await self._pg.mouse.click(animar["x"], animar["y"])
        self._log("  Clicked 'Animar' — waiting for video generation...")
        await asyncio.sleep(5)

        # Wait for new UUID (video placeholder)
        new_uuid = await self._wait_for_new_uuid(existing, timeout=120)
        if not new_uuid:
            self._log("  ERROR: no new UUID after Animar")
            return None

        # Poll until video ready (MP4 > 500KB)
        self._log("  Polling video until ready...")
        url, body = await self._poll_uuid_until_ready(
            new_uuid, min_size=200_000, interval=10, max_retries=40
        )
        if not body:
            self._log("  ERROR: animate video timeout")
            return None

        # Save
        dest = out_path or (CLIPS_DIR / f"animated_{new_uuid[:8]}.mp4")
        dest.write_bytes(body)
        self._log(f"  ✅ Animated video saved: {dest.name} ({len(body)/1024/1024:.1f}MB)")
        return dest

    # ── Image Generation (FREE) ──────────────────────────────────────────────

    async def generate_images(
        self,
        prompt: str,
        aspect_ratio: str = "9:16",
        count: int = 2,
        out_prefix: str = "img",
        reference_image: Path = None,
    ) -> list:
        """
        Generate images with Nano Banana / Imagen 4 (FREE tier).
        If reference_image provided, uploads it first as style reference.
        Returns list of saved PNG paths.
        """
        CAROUSEL_DIR.mkdir(parents=True, exist_ok=True)
        saved = []
        self._log(f"\n[IMAGE GEN] '{prompt[:60]}...' count={count}")

        if reference_image and reference_image.exists():
            await self._upload_image(reference_image)
            await self._dismiss_dialog()

        await self._switch_mode("Image")
        await self._set_aspect_ratio(aspect_ratio)
        existing = await self._get_page_uuids()
        # Inject optional style rotation bias (feature-flagged, advisory only)
        enhanced_prompt = self._inject_style_bias(prompt)
        await self._type_prompt(enhanced_prompt)
        await asyncio.sleep(0.5)

        await self._click_generate()
        await asyncio.sleep(3)

        deadline = time.time() + 180  # 3 min window for image generation
        collected: set = set()
        while len(saved) < count and time.time() < deadline:
            current = await self._get_page_uuids()
            new_uuids = (current - existing) - collected
            for uuid in list(new_uuids):
                url, body = await self._poll_uuid_until_ready(
                    uuid, min_size=50_000, interval=5, max_retries=12
                )
                if body and len(body) > 50_000:
                    idx = len(saved) + 1
                    out = CAROUSEL_DIR / f"{out_prefix}_{idx:02d}.png"
                    out.write_bytes(body)
                    saved.append(out)
                    collected.add(uuid)
                    self._log(f"  Image {idx}: {out.name} ({len(body)//1024}KB)")
            if len(saved) < count:
                await asyncio.sleep(5)

        self._log(f"  Saved {len(saved)}/{count} images")
        return saved

    # ── Video Scene Generation ────────────────────────────────────────────────

    async def generate_video_scene(self, scene: dict) -> bool:
        """
        Generate one video scene end-to-end with optional start+end frames.

        scene dict keys:
          image_input:       str — start frame filename (in ASSETS or FRAMES dir)
          end_frame_input:   str — (optional) end frame filename for Fin slot
          flow_prompt:       str — video generation prompt
          output_clip:       str — output MP4 filename
          last_frame_output: str — last frame PNG filename for continuity
          purpose:           str — scene label
          scene_id:          int

        If end_frame_input is provided, switches to Video+Fotogramas mode
        (Veo 3.1 with start+end frames). Otherwise uses standard Video mode.

        Timeline:
          [1] Switch to Video mode (+ Fotogramas if end frame)
          [2] Upload start frame → set Iniciar slot
          [3] Upload end frame  → set Fin slot (if provided)
          [4] Type prompt
          [5] Collect pre-gen UUIDs
          [6] Click Crear → wait for new UUID
          [7] Poll UUID until MP4 ready (3-8 min, 20 credits)
          [8] Save MP4 → extract last frame (FFmpeg)
        """
        sid = scene["scene_id"]
        use_end_frame = bool(scene.get("end_frame_input"))

        self._log(f"\n{'='*55}")
        self._log(f"SCENE {sid} — {scene['purpose']}"
                  + (" [start+end frames]" if use_end_frame else " [start frame]"))
        self._log(f"{'='*55}")

        # Resolve paths
        img_name = scene["image_input"]
        img_path = ASSETS_DIR / img_name if not img_name.startswith("scene_") else FRAMES_DIR / img_name
        out_clip  = CLIPS_DIR  / scene["output_clip"]
        out_frame = FRAMES_DIR / scene["last_frame_output"]

        if not img_path.exists():
            self._log(f"  ERROR: start frame not found: {img_path}")
            scene["status"] = "failed"
            scene["error"] = f"image not found: {img_path}"
            return False

        # Resolve end frame path
        end_path = None
        if use_end_frame:
            ef_name = scene["end_frame_input"]
            end_path = (ASSETS_DIR / ef_name if not ef_name.startswith("scene_")
                        else FRAMES_DIR / ef_name)
            if not end_path.exists():
                self._log(f"  WARNING: end frame not found: {end_path} — single-frame mode")
                use_end_frame = False

        await self._pg.screenshot(path=f"/tmp/s{sid}_start.png")

        # [1] Switch to correct mode
        # ALWAYS use Fotogramas mode when a start frame is provided — plain "Video" mode
        # (text-to-video) does NOT show the Iniciar slot, so start frame upload would fail.
        if use_end_frame:
            self._log("  [1] Switching to Video+Fotogramas mode...")
            if not await self._ensure_video_frames_mode(aspect_ratio="9:16"):
                self._log("  WARNING: could not enter frames mode — trying standard video")
                await self._switch_mode("Video")
        else:
            # Has start frame but no end frame → still need Fotogramas mode for Iniciar slot
            self._log("  [1] Switching to Video+Fotogramas mode (start frame only)...")
            if not await self._ensure_video_frames_mode(aspect_ratio="9:16"):
                self._log("  WARNING: could not enter frames mode — trying standard video")
                await self._switch_mode("Video")

        # [2] Upload start frame + set Iniciar slot
        self._log("  [2] Setting Iniciar (start frame)...")
        if not await self._upload_and_set_slot(img_path, slot="start"):
            scene["status"] = "failed"
            scene["error"] = "failed to set start frame"
            return False

        # [3] Upload end frame + set Fin slot (if provided)
        if use_end_frame:
            self._log("  [3] Setting Fin (end frame)...")
            if not await self._upload_and_set_slot(end_path, slot="end"):
                self._log("  WARNING: failed to set end frame — continuing anyway")

        await self._pg.screenshot(path=f"/tmp/s{sid}_slots.png")

        # [4] Type prompt (with optional style rotation bias)
        self._log("  [4] Typing prompt...")
        enhanced_prompt = self._inject_style_bias(scene["flow_prompt"])
        if not await self._type_prompt(enhanced_prompt):
            scene["status"] = "failed"
            scene["error"] = "prompt input not found"
            return False

        await self._pg.screenshot(path=f"/tmp/s{sid}_ready.png")

        # [5] Pre-collect UUIDs
        existing = await self._get_page_uuids()
        self._log(f"  Pre-gen UUIDs: {len(existing)}")

        # [6] Click Crear
        self._log("  [5] Clicking Crear...")
        await self._click_generate()
        await asyncio.sleep(5)
        await self._pg.screenshot(path=f"/tmp/s{sid}_generating.png")

        # Wait for new UUID (appears immediately as placeholder)
        self._log("  [6] Waiting for new UUID...")
        new_uuid = await self._wait_for_new_uuid(existing, timeout=180)  # extended: some scenes take >90s
        if not new_uuid:
            scene["status"] = "failed"
            scene["error"] = "no new UUID after generate"
            return False

        # [7] Poll until MP4 ready (JPEG ~84KB during gen → MP4 ~2MB+ when done)
        self._log("  [7] Polling until MP4 ready (~3-8 min, 20 credits)...")
        url, body = await self._poll_uuid_until_ready(
            new_uuid, min_size=500_000, interval=12, max_retries=50
        )
        if body is None:
            scene["status"] = "failed"
            scene["error"] = "video generation timeout"
            return False

        await self._pg.screenshot(path=f"/tmp/s{sid}_done.png")

        # [8] Save MP4
        CLIPS_DIR.mkdir(parents=True, exist_ok=True)
        out_clip.write_bytes(body)
        self._log(f"  Saved: {out_clip.name} ({len(body)/1024/1024:.2f} MB)")

        # Extract last frame for next scene continuity
        self._log("  [8] Extracting last frame...")
        self._extract_last_frame(out_clip, out_frame)

        scene["status"]        = "completed"
        scene["download_path"] = str(out_clip)
        scene["flow_url"]      = url
        self._log_event(sid, "completed", str(out_clip))
        self._log(f"  ✅ SCENE {sid} DONE")

        # Wait before next scene (Flow needs breathing room)
        self._log("  Waiting 10s before next scene...")
        await asyncio.sleep(10)
        return True

    # ── Frame Image Generation (FREE with Nano Banana) ───────────────────────

    async def generate_scene_frame_images(
        self,
        scene: dict,
        product_image: Path = None,
        aspect_ratio: str = "9:16",
    ) -> dict:
        """
        Generate start + end frame images for a scene using Nano Banana (FREE).
        Uses scene['start_frame_prompt'] and scene['end_frame_prompt'] if present,
        otherwise falls back to scene['flow_prompt'].

        Saves frames to FRAMES_DIR:
          scene_NN_start.png  — start frame
          scene_NN_end.png    — end frame

        Returns: {'start_frame': Path, 'end_frame': Path}
        """
        sid = scene["scene_id"]
        prefix = f"scene_{sid:02d}"
        FRAMES_DIR.mkdir(parents=True, exist_ok=True)
        result = {}

        self._log(f"\n[FRAMES] Scene {sid} — generating start+end frames (FREE)...")

        # Start frame
        start_prompt = (scene.get("start_frame_prompt")
                        or scene.get("image_prompt")
                        or scene.get("flow_prompt", ""))
        self._log(f"  Start: '{start_prompt[:70]}...'")

        start_imgs = await self.generate_images(
            prompt=start_prompt,
            aspect_ratio=aspect_ratio,
            count=1,
            out_prefix=f"{prefix}_start",
            reference_image=product_image,
        )
        if start_imgs:
            dest = FRAMES_DIR / f"{prefix}_start.png"
            shutil.copy(str(start_imgs[0]), str(dest))
            result["start_frame"] = dest
            self._log(f"  Start frame → {dest.name}")
        else:
            self._log(f"  ERROR: start frame generation failed for scene {sid}")
            return result

        # Wait between generations (Flow needs time)
        self._log("  Waiting 15s before end frame...")
        await asyncio.sleep(15)

        # End frame
        end_prompt = (scene.get("end_frame_prompt")
                      or scene.get("image_prompt")
                      or scene.get("flow_prompt", ""))
        # Make end prompt slightly different to get variation
        if end_prompt == start_prompt:
            end_prompt = end_prompt + ", final result, skin transformation complete"
        self._log(f"  End: '{end_prompt[:70]}...'")

        end_imgs = await self.generate_images(
            prompt=end_prompt,
            aspect_ratio=aspect_ratio,
            count=1,
            out_prefix=f"{prefix}_end",
            reference_image=product_image,
        )
        if end_imgs:
            dest = FRAMES_DIR / f"{prefix}_end.png"
            shutil.copy(str(end_imgs[0]), str(dest))
            result["end_frame"] = dest
            self._log(f"  End frame → {dest.name}")
        else:
            self._log(f"  WARNING: end frame generation failed — will use start only")

        return result

    # ── Amazon Research ──────────────────────────────────────────────────────

    async def research_amazon(self, keyword: str) -> dict:
        """
        Open Amazon, search keyword, screenshot + extract product info.
        Returns dict with: title, price, bullets, screenshots, main_image path.
        """
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        result = {"keyword": keyword, "screenshots": [], "title": "", "price": ""}
        ctx = self._browser.contexts[0]
        pg = await ctx.new_page()
        self._log(f"\n[AMAZON] '{keyword}'")
        try:
            await pg.goto(
                f"https://www.amazon.com/s?k={keyword.replace(' ','+')}&language=en_US",
                timeout=30000
            )
            await asyncio.sleep(3)
            ss1 = ASSETS_DIR / "amazon_search.png"
            await pg.screenshot(path=str(ss1))
            result["screenshots"].append(ss1)

            first = pg.locator('[data-component-type="s-search-result"] h2 a').first
            await first.click()
            await asyncio.sleep(3)

            info = await pg.evaluate("""
            () => ({
                title: document.querySelector('#productTitle')?.innerText?.trim() || '',
                price: document.querySelector('.a-price .a-offscreen')?.innerText?.trim() || '',
                bullets: Array.from(document.querySelectorAll('#feature-bullets li'))
                    .map(li=>li.innerText.trim()).filter(t=>t).slice(0,5),
            })
            """)
            result.update(info)
            self._log(f"  Product: {info.get('title','')[:60]}")

            ss2 = ASSETS_DIR / "amazon_product.png"
            await pg.screenshot(path=str(ss2))
            result["screenshots"].append(ss2)

            img_url = await pg.evaluate("""
            () => {
                const img = document.querySelector('#landingImage,#imgBlkFront');
                return img ? (img.getAttribute('data-old-hires') || img.src) : null;
            }
            """)
            if img_url:
                resp = await pg.request.get(img_url, timeout=20000)
                body = await resp.body()
                main = ASSETS_DIR / "amazon_product_main.jpg"
                main.write_bytes(body)
                result["main_image"] = main
                result["screenshots"].append(main)
                self._log(f"  Main image: {main.name} ({len(body)//1024}KB)")

        except Exception as e:
            self._log(f"  Amazon error: {e}")
        finally:
            await pg.close()
        return result

    # ── Pipeline Runner ──────────────────────────────────────────────────────

    async def run(self, generate_frames: bool = False, product_image: Path = None) -> dict:
        """
        Run all pending scenes. Returns updated plan.

        generate_frames: if True, generates start+end frame images with Nano Banana
                         BEFORE generating each video. Each scene gets two frames.
        product_image:   reference image for Nano Banana generation (optional).
        """
        plan = self.plan
        CLIPS_DIR.mkdir(parents=True, exist_ok=True)
        FRAMES_DIR.mkdir(parents=True, exist_ok=True)

        pending = [s for s in plan["scenes"] if s["status"] == "pending"]
        self._log(f"Pending scenes: {[s['scene_id'] for s in pending]}")
        if generate_frames:
            self._log("Mode: Image generation (FREE) → Video (credits)")
        else:
            self._log("Mode: Video only (uses start frame from plan)")

        for scene in pending:
            sid = scene["scene_id"]

            # Phase A: Generate start+end frame images with Nano Banana (FREE)
            if generate_frames:
                self._log(f"\n--- Generating frames for scene {sid} ---")
                frames = await self.generate_scene_frame_images(
                    scene, product_image=product_image
                )
                if frames.get("start_frame"):
                    # Update scene to use generated images
                    scene["image_input"] = frames["start_frame"].name
                    if frames.get("end_frame"):
                        scene["end_frame_input"] = frames["end_frame"].name
                else:
                    self._log(f"  Frame generation failed for scene {sid} — using fallback")

            # Phase B: Generate video
            ok = await self.generate_video_scene(scene)
            if not ok:
                self._log(f"Stopping at scene {scene['scene_id']}")
                break
            plan.setdefault("completed_scenes", [])
            if scene["scene_id"] not in plan["completed_scenes"]:
                plan["completed_scenes"].append(scene["scene_id"])

        return plan

    @classmethod
    def run_sync(
        cls,
        plan: dict,
        no_interactive: bool = False,
        generate_frames: bool = False,
        product_image: Path = None,
    ) -> dict:
        """Synchronous entry point for flow_agent.py."""
        async def _inner():
            op = cls(plan=plan, no_interactive=no_interactive)
            if not await op.connect():
                raise RuntimeError("Cannot connect to Chrome CDP port 9222")
            try:
                return await op.run(
                    generate_frames=generate_frames,
                    product_image=product_image,
                )
            finally:
                await op.close()
        return asyncio.run(_inner())

    # ── Logging ─────────────────────────────────────────────────────────────

    def _log(self, msg: str):
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {msg}", flush=True)
        self.execution_log.append({"ts": ts, "msg": msg})

    def _log_event(self, scene_id: int, event: str, path: str = ""):
        self.execution_log.append({"scene_id": scene_id, "event": event, "path": path})


# ─── STANDALONE ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Google Flow operator (Playwright CDP)")
    parser.add_argument("--plan", required=True, help="Path to scene plan JSON")
    parser.add_argument("--scene", type=int, default=None, help="Run single scene by ID")
    parser.add_argument("--amazon", default=None, help="Amazon keyword for research")
    parser.add_argument("--frames", action="store_true",
                        help="Generate start+end frame images with Nano Banana before each video")
    parser.add_argument("--product-image", default=None,
                        help="Local product image path for Nano Banana reference")
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text())
    if args.scene:
        plan["scenes"] = [s for s in plan["scenes"] if s["scene_id"] == args.scene]

    prod_img = Path(args.product_image) if args.product_image else None

    async def _main():
        op = FlowOperator(plan)
        await op.connect()
        if args.amazon:
            print(await op.research_amazon(args.amazon))
        plan_out = await op.run(
            generate_frames=args.frames,
            product_image=prod_img,
        )
        done = len(plan_out.get("completed_scenes", []))
        print(f"\nDone: {done}/{plan_out.get('total_scenes', '?')} scenes")
        await op.close()

    asyncio.run(_main())

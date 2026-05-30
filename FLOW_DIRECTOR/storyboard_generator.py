#!/usr/bin/env python3
"""
storyboard_generator.py — IMPERIO Cinematic Storyboard Generator

FLUJO:
  1. Fetch imagen REAL del producto desde Amazon (ASIN)
  2. Genera 12 prompts específicos por escena via Ollama
  3. Genera storyboard grid 4x4 via Nano Banana (GRATIS)
     — product image como style reference
  4. Envía storyboard a Telegram para review
  5. Si aprobado: retorna prompts por escena para Veo 3.1
"""

import asyncio
import json
import os
import sys
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

BASE_DIR   = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FLOW_DIRECTOR")
REVENUE_DIR= Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE")
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"
STORYBOARDS_DIR = BASE_DIR / "storyboards"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:1.5b"

# ── Load env ──────────────────────────────────────────────────────────────────

def load_env():
    for p in [Path.home() / "IMPERIO_NUCLEO/.env",
              Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/.env")]:
        if p.exists():
            for line in p.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"'))

load_env()

TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT   = os.environ.get("TELEGRAM_CHAT_ID", "")

# ── Amazon Product Image ──────────────────────────────────────────────────────

def fetch_amazon_product_image(asin: str, out_path: Path) -> bool:
    """
    Fetch real product image from Amazon CDN.
    Uses playwright CDP if available; falls back to direct CDN guess.
    Returns True if image saved successfully.
    """
    # Try Playwright CDP to get real main image
    try:
        from playwright.async_api import async_playwright

        async def _fetch():
            pw = await async_playwright().start()
            browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
            ctx = browser.contexts[0]
            # Open Amazon product page in a new tab
            page = await ctx.new_page()
            url = f"https://www.amazon.com/dp/{asin}"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Get main image URL
            img_url = await page.evaluate("""
            () => {
                // Main product image selectors (Amazon)
                const selectors = [
                    '#landingImage',
                    '#imgBlkFront',
                    '.a-dynamic-image',
                    '#main-image',
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) {
                        return el.getAttribute('data-old-hires') ||
                               el.getAttribute('data-a-hires') ||
                               el.src;
                    }
                }
                return null;
            }
            """)

            await page.close()
            await browser.close()
            await pw.stop()
            return img_url

        img_url = asyncio.run(_fetch())
        if img_url:
            print(f"[storyboard] Amazon image URL: {img_url[:80]}")
            urllib.request.urlretrieve(img_url, str(out_path))
            if out_path.exists() and out_path.stat().st_size > 10000:
                print(f"[storyboard] ✅ Real product image saved: {out_path.name} ({out_path.stat().st_size//1024}KB)")
                return True
    except Exception as e:
        print(f"[storyboard] Playwright fetch failed: {e}")

    # Fallback: try Amazon CDN direct URLs
    cdn_templates = [
        f"https://m.media-amazon.com/images/P/{asin}.01._SCLZZZZZZZ_SX500_.jpg",
        f"https://images-na.ssl-images-amazon.com/images/P/{asin}.01.LZZZZZZZ.jpg",
    ]
    for url in cdn_templates:
        try:
            urllib.request.urlretrieve(url, str(out_path))
            if out_path.exists() and out_path.stat().st_size > 10000:
                print(f"[storyboard] ✅ CDN image saved: {out_path.name}")
                return True
        except Exception:
            continue

    print("[storyboard] ⚠️  Could not fetch real product image — using existing asset")
    return False

# ── Scene Prompt Generation ───────────────────────────────────────────────────

SCENE_ROLES = [
    ("INTRO",      "Product package pristine on clean surface, studio lighting, dramatic shadow"),
    ("UNBOX",      "Hands opening product package, reveal moment"),
    ("DETAIL",     "Close-up product container/packaging premium texture"),
    ("EXTRACT",    "Single pad/product unit extracted, held between fingers"),
    ("TEXTURE",    "Extreme close-up of product surface texture and material"),
    ("BEFORE",     "Close-up of skin showing the problem the product solves"),
    ("APPLY",      "Applying product to skin, gentle motion, precise hands"),
    ("CONTACT",    "Product touching skin, close-up of application point"),
    ("REACTION",   "Immediate skin response after application, glossy/dewy"),
    ("TRANSFORM",  "Visible transformation of skin, before/after comparison"),
    ("LIFESTYLE",  "Person with glowing results, natural lifestyle setting"),
    ("HERO",       "Final hero shot: product floating/floating, soft glow, clean background"),
]

def generate_scene_prompts_ollama(product: dict) -> list[dict]:
    """
    Generate 12 scene-specific prompts via Ollama.
    Each prompt explicitly references the real product appearance.
    """
    name     = product["name"]
    price    = product.get("price", "")
    category = product.get("category", "skincare")
    angle    = product.get("video_angle", "transforms your routine")

    system = f"""You are a professional commercial storyboard prompt writer.

Product: {name}
Price: ${price}
Category: {category}
Marketing angle: {angle}

Rules:
- Every prompt MUST visually reference the REAL product (its actual package, color, label)
- Product package is always identifiable and consistent
- Ultra-realistic, cinematic, commercial photography quality
- 9:16 vertical aspect ratio (TikTok/Reels)
- Max 80 words per prompt
- No invented products — the real product must be recognizable"""

    scenes = []
    for i, (role, base_action) in enumerate(SCENE_ROLES, 1):
        user_msg = f"""Write a single cinematic image prompt for storyboard frame {i} of 12.

Scene role: {role}
Base action: {base_action}

The REAL product ({name}) must be clearly visible and identifiable.

Respond with only the prompt text, no explanation."""

        payload = {
            "model": OLLAMA_MODEL,
            "system": system,
            "prompt": user_msg,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 120}
        }

        try:
            req = urllib.request.Request(
                OLLAMA_URL,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"}
            )
            resp = urllib.request.urlopen(req, timeout=30)
            result = json.loads(resp.read())
            prompt_text = result.get("response", "").strip()
        except Exception as e:
            print(f"[storyboard] Ollama scene {i} failed: {e}")
            prompt_text = (
                f"Ultra-realistic cinematic product shot of {name}, "
                f"{base_action.lower()}, professional commercial photography, "
                f"9:16 vertical, dramatic studio lighting"
            )

        scenes.append({
            "frame": i,
            "role": role,
            "action": base_action,
            "prompt": prompt_text,
        })
        print(f"[storyboard] Scene {i:02d} ({role}): {prompt_text[:60]}...")

    return scenes

# ── Storyboard Grid Prompt ────────────────────────────────────────────────────

def build_storyboard_grid_prompt(product: dict, scenes: list[dict]) -> str:
    """
    Build ONE master prompt for Nano Banana to generate the 4x4 storyboard grid.
    All 12 frames must show the real product consistently.
    """
    name = product["name"]

    frame_descriptions = "\n".join(
        f"Frame {s['frame']}: {s['role']} — {s['action']}"
        for s in scenes
    )

    return f"""Create a professional 4x4 storyboard grid, 16 panels total.

Layout: 12 filled story frames (numbered 1-12) + 4 empty gray placeholder frames (13-16).

VISUAL RULES:
- Thin black borders separating every frame
- Bold sans-serif frame numbers (1-12) in top-left corner
- Short caption under each frame
- Frames 13-16: blank/subtle gray, no numbers
- EVERY frame must prominently feature the REAL product: {name}
- Product packaging color, label, and design must be IDENTICAL across all frames
- Ultra-realistic cinematic photography quality
- 9:16 vertical composition

STORY SEQUENCE:
{frame_descriptions}

STYLE: Ultra-realistic, commercial photography, dramatic studio lighting,
consistent product appearance, professional storyboard illustration quality,
sharp product details, TikTok/Reels vertical format"""

# ── Storyboard Generation via Flow ───────────────────────────────────────────

def render_storyboard_grid_pil(
    scenes: list[dict],
    product_img: Path,
    product: dict,
) -> Path:
    """
    Render 4x4 storyboard grid using PIL (always works, no AI credits).
    12 active frames with scene info + product thumbnail.
    4 empty placeholder frames.
    Returns path to saved PNG.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        raise RuntimeError("pip install Pillow")

    COLS, ROWS   = 4, 4
    FW, FH       = 380, 230   # frame width/height
    CAPTION_H    = 36
    BORDER       = 3
    HEADER_H     = 55
    BG           = (14, 14, 14)
    FRAME_BG     = (26, 26, 26)
    BORDER_CLR   = (55, 55, 55)
    EMPTY_CLR    = (34, 34, 34)
    TEXT_CLR     = (220, 220, 220)
    DIM_CLR      = (130, 130, 130)
    NUM_CLR      = (255, 215, 50)
    ROLE_CLR     = (90, 200, 120)

    total_w = BORDER + COLS * (FW + BORDER)
    total_h = HEADER_H + BORDER + ROWS * (FH + CAPTION_H + BORDER)

    canvas = Image.new("RGB", (total_w, total_h), BG)
    draw   = ImageDraw.Draw(canvas)

    def font(size):
        for p in ["/System/Library/Fonts/Helvetica.ttc",
                  "/System/Library/Fonts/Arial.ttf",
                  "/Library/Fonts/Arial.ttf"]:
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
        return ImageFont.load_default()

    f_num     = font(34)
    f_role    = font(13)
    f_text    = font(11)
    f_caption = font(11)
    f_title   = font(18)

    # Header
    title = f"{product.get('name','')[:56]}  ·  Storyboard {datetime.now().strftime('%Y-%m-%d')}"
    draw.text((BORDER + 8, 12), title, fill=TEXT_CLR, font=f_title)

    # Product thumbnail
    thumb = None
    if product_img and Path(product_img).exists():
        try:
            img = Image.open(product_img).convert("RGB")
            img.thumbnail((80, 80), Image.LANCZOS)
            thumb = img
        except Exception:
            pass

    for idx in range(ROWS * COLS):
        col = idx % COLS
        row = idx // COLS
        x0  = BORDER + col * (FW + BORDER)
        y0  = HEADER_H + BORDER + row * (FH + CAPTION_H + BORDER)
        x1, y1 = x0 + FW, y0 + FH

        if idx < 12:
            s = scenes[idx]
            draw.rectangle([x0, y0, x1, y1], fill=FRAME_BG, outline=BORDER_CLR, width=BORDER)

            # Frame number
            draw.text((x0 + 8, y0 + 5), str(s["frame"]), fill=NUM_CLR, font=f_num)

            # Role label (top-right)
            role = s.get("role", "")
            draw.text((x1 - 85, y0 + 8), role, fill=ROLE_CLR, font=f_role)

            # Product thumbnail bottom-right
            if thumb:
                tw, th = thumb.size
                paste_x, paste_y = x1 - tw - 6, y1 - th - 6
                canvas.paste(thumb, (paste_x, paste_y))
                draw.rectangle([paste_x-1, paste_y-1, paste_x+tw+1, paste_y+th+1],
                                outline=(70,70,70), width=1)

            # Scene description (wrapped)
            desc = s.get("action", s.get("prompt", ""))[:100]
            import textwrap
            lines = textwrap.wrap(desc, width=40)
            ty = y0 + 52
            for line in lines[:4]:
                draw.text((x0 + 8, ty), line, fill=DIM_CLR, font=f_text)
                ty += 14

            # Caption below frame
            draw.text((x0 + 4, y1 + 4),
                      f"Frame {s['frame']}: {role}",
                      fill=(100, 100, 100), font=f_caption)
        else:
            # Empty placeholder
            draw.rectangle([x0, y0, x1, y1], fill=EMPTY_CLR, outline=BORDER_CLR, width=BORDER)
            cx, cy = x0 + FW // 2 - 22, y0 + FH // 2 - 6
            draw.text((cx, cy), "[ empty ]", fill=(50, 50, 50), font=f_caption)

    STORYBOARDS_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = STORYBOARDS_DIR / f"storyboard_{ts}.png"
    canvas.save(path, "PNG")
    print(f"[storyboard] ✅ PIL grid: {path.name} ({path.stat().st_size//1024}KB)")
    return path

# ── Telegram Review ───────────────────────────────────────────────────────────

def send_storyboard_for_review(storyboard_path: Path, product: dict, scenes: list[dict]) -> bool:
    """
    Send storyboard image + scene prompts to Telegram for review.
    Returns True if message sent.
    """
    if not TELEGRAM_TOKEN:
        print("[storyboard] No Telegram token — skipping review send")
        return False

    # Send image
    try:
        img_data = storyboard_path.read_bytes()
        boundary = "----SBBoundary"
        body_parts = []

        for k, v in {"chat_id": TELEGRAM_CHAT, "caption": f"🎬 STORYBOARD: {product['name'][:40]}"}.items():
            body_parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
            )

        body_parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"storyboard.png\"\r\nContent-Type: image/png\r\n\r\n".encode()
            + img_data + b"\r\n"
        )
        body_parts.append(f"--{boundary}--\r\n".encode())
        body = b"".join(body_parts)

        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        urllib.request.urlopen(req, timeout=60)
        print("[storyboard] ✅ Storyboard image sent to Telegram")
    except Exception as e:
        print(f"[storyboard] Image send failed: {e}")
        return False

    # Send scene prompts as text
    scenes_text = "\n".join(
        f"F{s['frame']} {s['role']}: {s['prompt'][:100]}..."
        for s in scenes
    )

    msg = (
        f"📋 STORYBOARD REVIEW — {product['name'][:40]}\n\n"
        f"12 escenas generadas. Prompts por frame:\n\n{scenes_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ /approve — Generar videos con estos prompts (Veo 3.1)\n"
        f"❌ /reject — Regenerar storyboard\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━"
    )

    try:
        data = json.dumps({
            "chat_id": TELEGRAM_CHAT,
            "text": msg
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        urllib.request.urlopen(req, timeout=30)
        return True
    except Exception as e:
        print(f"[storyboard] Prompt text send failed: {e}")
        return False

# ── Save Scene Plan ───────────────────────────────────────────────────────────

def save_scene_plan(product: dict, scenes: list[dict], storyboard_path: Path) -> Path:
    """Save scene prompts JSON for later Veo 3.1 video generation."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    plan = {
        "created_at": datetime.now().isoformat(),
        "product": product["name"],
        "asin": product.get("asin"),
        "affiliate_url": product.get("affiliate_url"),
        "storyboard_image": str(storyboard_path),
        "scenes": scenes,
        "video_ready": False,  # set True after Veo 3.1 generation
    }

    plan_path = OUTPUT_DIR / f"storyboard_plan_{ts}.json"
    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
    print(f"[storyboard] Plan saved: {plan_path.name}")
    return plan_path

# ── Main ──────────────────────────────────────────────────────────────────────

def run(product: dict) -> Path | None:
    """
    Full storyboard generation pipeline for one product.
    Returns path to scene plan JSON (ready for Veo 3.1).
    """
    name = product["name"]
    asin = product.get("asin", "")

    print(f"\n{'='*60}")
    print(f"  STORYBOARD GENERATOR — {name[:50]}")
    print(f"{'='*60}\n")

    # 1. Real product image
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    safe_asin = asin if asin else "unknown"
    product_img = ASSETS_DIR / f"product_{safe_asin}.jpg"

    if not product_img.exists() or product_img.stat().st_size < 10000:
        print(f"[storyboard] Fetching real product image (ASIN: {asin})...")
        fetched = fetch_amazon_product_image(asin, product_img)
        if not fetched:
            # Use existing product_main.jpg as fallback
            product_img = ASSETS_DIR / "product_main.jpg"
    else:
        print(f"[storyboard] Using cached product image: {product_img.name}")

    # 2. Generate 12 scene prompts
    print("\n[storyboard] Generating 12 scene prompts via Ollama...")
    scenes = generate_scene_prompts_ollama(product)

    # 3. Render storyboard grid via PIL (always correct, no AI credits)
    #    NOTE: Nano Banana/image AI cannot reliably render grid layouts with
    #    numbered frames and text — PIL guarantees correct output every time.
    #    Nano Banana is used later for individual SCENE images, not the grid.
    print("\n[storyboard] Rendering storyboard grid (PIL)...")
    storyboard_path = render_storyboard_grid_pil(scenes, product_img, product)

    if not storyboard_path:
        print("[storyboard] ❌ Storyboard render failed")
        return None

    # 5. Save scene plan
    plan_path = save_scene_plan(product, scenes, storyboard_path)

    # 6. Send to Telegram for review
    print("\n[storyboard] Sending to Telegram for review...")
    send_storyboard_for_review(storyboard_path, product, scenes)

    print("\n✅ Storyboard complete.")
    print(f"   Image: {storyboard_path}")
    print(f"   Plan:  {plan_path}")
    print("   → Review in Telegram → /approve to generate videos")
    return plan_path

# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="IMPERIO Storyboard Generator")
    parser.add_argument("--product", help="Product name (ignored if --from-brief used)")
    parser.add_argument("--asin",    default="",    help="Amazon ASIN")
    parser.add_argument("--price",   default="",    help="Product price")
    parser.add_argument("--angle",   default="transforms your daily routine",
                        help="Marketing angle")
    parser.add_argument("--affiliate", default="", help="Affiliate URL")
    parser.add_argument("--from-brief", action="store_true",
                        help="Load top product from daily_brief.json")

    args = parser.parse_args()

    if not args.from_brief and not args.product:
        parser.error("--product is required (or use --from-brief)")

    if args.from_brief:
        brief_path = REVENUE_DIR / "daily_brief.json"
        if not brief_path.exists():
            print("❌ No daily_brief.json found")
            sys.exit(1)
        brief = json.loads(brief_path.read_text())
        product = brief["products"][0]
    else:
        product = {
            "name": args.product,
            "asin": args.asin,
            "price": args.price,
            "video_angle": args.angle,
            "affiliate_url": args.affiliate,
        }

    plan = run(product)
    sys.exit(0 if plan else 1)

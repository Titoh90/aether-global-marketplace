"""
fooocus_executor.py — Fooocus image generation for IMPERIO Operator
Generates product images via Fooocus (simpler than ComfyUI, auto-downloads SDXL).

Usage from gateway:
  /fooocus_start                    → launch Fooocus web UI (port 7860)
  /fooocus "product photo watch"   → generate via API (when UI running)
  /fooocus_status                   → check status

Use case:
  - Generate product images for Amazon listings
  - Create ad creatives for TikTok/Instagram
  - Produce Fiverr client deliverables (AI product photos)
  - First run: auto-downloads SDXL Turbo (~7GB) — one time only

Web UI: http://localhost:7860 after /fooocus_start
"""

import subprocess
import logging
import json
import time
from pathlib import Path
from datetime import datetime

log = logging.getLogger("fooocus_executor")

FOOOCUS_DIR = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FOOOCUS")
VENV_PYTHON = FOOOCUS_DIR / "venv/bin/python"
LOGS_DIR    = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator/logs/fooocus")
OUTPUT_DIR  = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE/fooocus_images")

_fooocus_proc = None


def is_ready() -> bool:
    """Check if Fooocus venv is functional."""
    if not VENV_PYTHON.exists():
        return False
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", "import torch; import gradio; print('ok')"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0 and "ok" in result.stdout
    except Exception:
        return False


def start_web_ui(port: int = 7860, listen: bool = False) -> dict:
    """
    Launch Fooocus web UI.
    First run: downloads SDXL Turbo model (~7GB) — takes 10-20 minutes.
    After first run: launches in ~30 seconds.

    Args:
        port: Port for web UI (default 7860)
        listen: Expose to LAN (0.0.0.0) for access from other devices

    Returns immediately — UI runs in background.
    """
    global _fooocus_proc
    if _fooocus_proc and _fooocus_proc.poll() is None:
        return {"status": "already_running", "url": f"http://localhost:{port}"}

    if not is_ready():
        return {"status": "failed", "error": "Fooocus not installed. Run: install_fooocus.sh"}

    # Output dir for generated images
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(VENV_PYTHON), str(FOOOCUS_DIR / "entry_with_update.py"),
        "--port", str(port),
        "--output-path", str(OUTPUT_DIR),
    ]
    if listen:
        cmd.append("--listen")

    _fooocus_proc = subprocess.Popen(
        cmd,
        cwd=str(FOOOCUS_DIR),
        env={
            **__import__("os").environ,
            "PYTORCH_ENABLE_MPS_FALLBACK": "1",
        }
    )
    log.info(f"Fooocus started PID {_fooocus_proc.pid} → http://localhost:{port}")
    return {
        "status": "started",
        "pid": _fooocus_proc.pid,
        "url": f"http://localhost:{port}",
        "note": (
            "First launch downloads SDXL model (~7GB, one-time). "
            "Subsequent launches: ~30s. "
            "Use web UI for image generation."
        ),
    }


def stop_web_ui() -> dict:
    """Stop Fooocus web UI."""
    global _fooocus_proc
    if _fooocus_proc and _fooocus_proc.poll() is None:
        _fooocus_proc.terminate()
        _fooocus_proc = None
        return {"status": "stopped"}
    return {"status": "not_running"}


def generate_via_api(prompt: str, negative_prompt: str = "",
                      style: str = "Fooocus V2", aspect: str = "9:16",
                      count: int = 1) -> dict:
    """
    Generate images via Fooocus HTTP API (requires web UI running).
    UI must be started with start_web_ui() first.

    Args:
        prompt: Image description
        negative_prompt: Things to avoid
        style: Fooocus style preset ("Fooocus V2", "Anime", "Photography", etc.)
        aspect: "9:16" (TikTok/Reels), "1:1" (Instagram), "16:9" (YouTube)
        count: Number of images to generate

    Returns:
        {"status": "success", "images": ["/path/to/img1.png", ...]}
    """
    import urllib.request

    ASPECT_MAP = {
        "9:16": (896, 1152),
        "1:1":  (1024, 1024),
        "16:9": (1280, 720),
        "4:3":  (1152, 896),
        "3:4":  (896, 1152),
    }
    w, h = ASPECT_MAP.get(aspect, (896, 1152))

    payload = json.dumps({
        "prompt": prompt,
        "negative_prompt": negative_prompt or "ugly, blurry, watermark, low quality",
        "style_selections": [style],
        "performance_selection": "Speed",
        "aspect_ratios_selection": f"{w}×{h}",
        "image_number": count,
        "image_seed": -1,
        "sharpness": 2.0,
        "guidance_scale": 4.0,
        "base_model_name": "juggernautXL_v8Rundiffusion.safetensors",
    }).encode()

    try:
        req = urllib.request.Request(
            "http://localhost:7860/v1/generation/text-to-image",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            result = json.loads(r.read())

        images = [item.get("url") or item.get("path") for item in result
                  if isinstance(item, dict)]
        images = [img for img in images if img]

        _log_job(prompt, images)
        return {"status": "success", "images": images, "count": len(images)}
    except Exception as e:
        return {
            "status": "failed",
            "error": str(e),
            "note": "Ensure Fooocus UI is running: /fooocus_start",
        }


def generate_product_image(product_name: str, style: str = "Photography",
                            background: str = "white studio", count: int = 4) -> dict:
    """Pre-built product image generator for Amazon/Fiverr."""
    prompt = (
        f"professional product photography of {product_name}, "
        f"{background} background, studio lighting, 8k, sharp focus, "
        f"commercial photography, isolated product"
    )
    neg = "person, model, watermark, text, logo, blurry, cartoon"
    return generate_via_api(prompt, neg, style, "1:1", count)


def get_status() -> dict:
    global _fooocus_proc
    running = _fooocus_proc and _fooocus_proc.poll() is None
    return {
        "venv": "ready" if VENV_PYTHON.exists() else "missing",
        "dependencies": "installed" if is_ready() else "not_installed",
        "web_ui": "running" if running else "stopped",
        "web_url": "http://localhost:7860" if running else None,
        "output_dir": str(OUTPUT_DIR),
        "note": "First run downloads SDXL model ~7GB",
    }


def _log_job(prompt: str, images: list):
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOGS_DIR / f"fooocus_{today}.jsonl"
        entry = {"ts": datetime.now().isoformat(), "prompt": prompt[:200], "images": images}
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

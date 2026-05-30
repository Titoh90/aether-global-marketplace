"""
FLOW EXECUTOR — Wrapper real de FLOW_DIRECTOR
Ejecuta generate_video y generate_image via subprocess.
Requiere: Chrome con --remote-debugging-port=9222 activo.
"""
import subprocess
import socket
import json
import logging
from pathlib import Path

log = logging.getLogger("flow_executor")

FLOW_DIR    = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FLOW_DIRECTOR")
CAROUSEL_DIR = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE/carousels")
PYTHON      = "/opt/homebrew/bin/python3.14"


def chrome_cdp_active() -> bool:
    """Check if Chrome remote debugging is up."""
    try:
        s = socket.create_connection(("127.0.0.1", 9222), timeout=1)
        s.close()
        return True
    except:
        return False


def generate_video(params: dict, task_id: str) -> dict:
    """
    Executes Flow Director pipeline.
    params: {product, angle, platform}
    Returns: {status, output_path, logs}
    """
    if not chrome_cdp_active():
        return {
            "status": "failed",
            "error": "Chrome CDP no está activo. Lanza Chrome con --remote-debugging-port=9222 primero.",
            "task_id": task_id
        }

    product  = params.get("product", "luxury product")
    angle    = params.get("angle", "premium quality and style")
    platform = params.get("platform", "tiktok")

    cmd = [
        PYTHON, str(FLOW_DIR / "flow_agent.py"),
        "--product", product,
        "--angle", angle,
        "--platform", platform,
        "--yes"
    ]

    log.info(f"Launching Flow: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(FLOW_DIR),
            capture_output=True,
            text=True,
            timeout=600  # 10 min max (Veo3 takes 3-8 min)
        )

        output_dir = FLOW_DIR / "output"
        # Find newest MP4 in output
        mp4_files = sorted(output_dir.glob("**/*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True)
        video_path = str(mp4_files[0]) if mp4_files else None

        if result.returncode == 0:
            return {
                "status": "success",
                "output_path": video_path,
                "stdout_tail": result.stdout[-500:],
                "task_id": task_id
            }
        else:
            return {
                "status": "failed",
                "error": result.stderr[-300:] or result.stdout[-300:],
                "task_id": task_id
            }

    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "Timeout (10 min). Video generation too slow.", "task_id": task_id}
    except Exception as e:
        return {"status": "failed", "error": str(e), "task_id": task_id}


def generate_image(params: dict, task_id: str) -> dict:
    """Generate image only via Flow (Nano Banana — GRATIS)."""
    if not chrome_cdp_active():
        return {
            "status": "failed",
            "error": "Chrome CDP no activo.",
            "task_id": task_id
        }

    product = params.get("product", "product")

    # Direct image generation script
    script = f"""
import asyncio, sys
sys.path.insert(0, "{FLOW_DIR}")
from flow_operator import FlowOperator

async def main():
    op = FlowOperator()
    await op.connect()
    imgs = await op.generate_image(
        prompt="professional product photography of {product}, white background, 9:16, commercial quality",
        out_dir="{FLOW_DIR}/output"
    )
    print("IMAGES:", ",".join(imgs))

asyncio.run(main())
"""

    try:
        result = subprocess.run(
            [PYTHON, "-c", script],
            capture_output=True, text=True, timeout=120
        )
        if "IMAGES:" in result.stdout:
            paths = result.stdout.split("IMAGES:")[-1].strip().split(",")
            return {
                "status": "success",
                "output_paths": paths,
                "task_id": task_id
            }
        return {"status": "failed", "error": result.stderr[:300], "task_id": task_id}
    except Exception as e:
        return {"status": "failed", "error": str(e), "task_id": task_id}


def generate_carousel(params: dict, task_id: str) -> dict:
    """
    Generate product carousel via carousel_flow.py (Google Flow / Nano Banana — FREE).
    params: {product, category, price, rating, features, slides}
    Returns: {status, output_paths, slide_count, output_dir}
    """
    if not chrome_cdp_active():
        return {
            "status": "failed",
            "error": "Chrome CDP no activo en :9222. Abre Chrome con --remote-debugging-port=9222.",
            "task_id": task_id,
        }

    product  = params.get("product", "product")
    category = params.get("category", "general")
    price    = params.get("price", "")
    rating   = params.get("rating", "")
    features = params.get("features", "")
    slides   = int(params.get("slides", 5))

    carousel_script = FLOW_DIR / "carousel_flow.py"

    cmd = [
        PYTHON, str(carousel_script),
        "--product", product,
        "--category", category,
        "--slides", str(slides),
        "--aspect", "1:1",
        "--overlay",
    ]
    if price:
        cmd += ["--price", price]
    if rating:
        cmd += ["--rating", rating]
    if features:
        cmd += ["--features", features]

    log.info(f"[{task_id}] carousel_flow: {product!r} ({slides} slides, cat={category})")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(FLOW_DIR),
            capture_output=True,
            text=True,
            timeout=900,  # 15 min max (5 slides × ~3 min each)
        )

        # Find manifest in output dir
        slug = product.lower().replace(" ", "_").replace("/", "_")[:40]
        manifest_path = CAROUSEL_DIR / f"{slug}_flow" / "manifest.json"

        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            slide_paths = manifest.get("slides", [])
            return {
                "status": "success",
                "output_paths": slide_paths,
                "output_path": slide_paths[0] if slide_paths else "",
                "slide_count": len(slide_paths),
                "output_dir": str(manifest_path.parent),
                "task_id": task_id,
            }

        # Fallback: parse stdout for "Generated slides:" block
        if result.returncode == 0:
            paths = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("/") and ".png" in line:
                    paths.append(line)
            if paths:
                return {
                    "status": "success",
                    "output_paths": paths,
                    "output_path": paths[0],
                    "slide_count": len(paths),
                    "task_id": task_id,
                }
            return {"status": "failed", "error": "No slides found in output.", "task_id": task_id}

        return {"status": "failed", "error": result.stderr[-300:] or result.stdout[-300:], "task_id": task_id}

    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "Timeout (15 min). Carousel took too long.", "task_id": task_id}
    except Exception as e:
        return {"status": "failed", "error": str(e), "task_id": task_id}

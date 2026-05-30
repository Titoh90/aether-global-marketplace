"""
esrgan_executor.py — Real-ESRGAN image upscaling for IMPERIO Operator
Upscales images 4x using Real-ESRGAN (replaces Topaz Photo AI).

Usage from gateway:
  /upscale /path/to/image.jpg         → upscale 4x, save beside original
  /upscale /path/to/image.jpg 2       → upscale 2x
  /upscale_batch /path/to/folder/     → batch upscale all images in folder

Requirements: pip installed in REAL_ESRGAN/venv
"""

import subprocess
import logging
import json
from pathlib import Path
from datetime import datetime

log = logging.getLogger("esrgan_executor")

ESRGAN_DIR  = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REAL_ESRGAN")
VENV_PYTHON = ESRGAN_DIR / "venv/bin/python"
MODELS_DIR  = ESRGAN_DIR / "models"
LOGS_DIR    = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator/logs/esrgan")
OUTPUT_DIR  = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE/upscaled")

MODEL_URL  = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
MODEL_FILE = MODELS_DIR / "RealESRGAN_x4plus.pth"

MODEL_URL_2X  = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth"


def is_ready() -> bool:
    """Check if Real-ESRGAN venv and model are ready."""
    if not VENV_PYTHON.exists():
        return False
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", "import realesrgan; print('ok')"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


def download_model(scale: int = 4) -> bool:
    """Download RealESRGAN model if not present."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_file = MODELS_DIR / "RealESRGAN_x4plus.pth"
    if model_file.exists() and model_file.stat().st_size > 1_000_000:
        return True
    log.info("Downloading RealESRGAN model (~64MB)...")
    try:
        import urllib.request
        urllib.request.urlretrieve(MODEL_URL, str(model_file))
        return model_file.stat().st_size > 1_000_000
    except Exception as e:
        log.error(f"Model download failed: {e}")
        return False


def upscale_image(input_path: str, scale: int = 4, face_enhance: bool = False) -> dict:
    """
    Upscale a single image using Real-ESRGAN.
    Returns: {"status": "success", "output": "/path/to/output.png", "scale": 4}
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    input_path = Path(input_path)
    if not input_path.exists():
        return {"status": "failed", "error": f"Input not found: {input_path}"}

    if not is_ready():
        return {"status": "failed", "error": "Real-ESRGAN not installed. Run: install_esrgan.sh"}

    if not MODEL_FILE.exists():
        if not download_model(scale):
            return {"status": "failed", "error": "Model download failed"}

    # Output path: beside original, with _upscale4x suffix
    suffix = f"_upscale{scale}x"
    out_name = input_path.stem + suffix + ".png"
    out_path = OUTPUT_DIR / out_name

    cmd = [
        str(VENV_PYTHON),
        str(ESRGAN_DIR / "inference_realesrgan.py"),
        "-n", "RealESRGAN_x4plus",
        "-i", str(input_path),
        "-o", str(OUTPUT_DIR),
        "--outscale", str(scale),
        "--model_path", str(MODEL_FILE),
    ]
    if face_enhance:
        cmd.append("--face_enhance")

    log.info(f"Upscaling: {input_path.name} → {scale}x")
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
            cwd=str(ESRGAN_DIR)
        )
        if result.returncode != 0:
            return {"status": "failed", "error": result.stderr[-500:]}

        # Real-ESRGAN appends _out to filename
        out_files = list(OUTPUT_DIR.glob(f"{input_path.stem}_out*.png"))
        actual_out = str(out_files[0]) if out_files else str(out_path)

        _log_job(str(input_path), actual_out, scale)
        return {
            "status": "success",
            "input": str(input_path),
            "output": actual_out,
            "scale": scale,
        }
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "Timeout after 5 minutes"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def upscale_batch(folder_path: str, scale: int = 4) -> dict:
    """
    Upscale all images in a folder.
    Returns summary with success/failed counts.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        return {"status": "failed", "error": f"Not a directory: {folder_path}"}

    images = list(folder.glob("*.jpg")) + list(folder.glob("*.png")) + list(folder.glob("*.jpeg"))
    if not images:
        return {"status": "failed", "error": "No images found in folder"}

    results = {"sent": [], "failed": [], "total": len(images)}
    for img in images:
        r = upscale_image(str(img), scale)
        if r["status"] == "success":
            results["sent"].append(r["output"])
        else:
            results["failed"].append({"file": str(img), "error": r.get("error", "")})

    results["success_rate"] = f"{len(results['sent'])}/{results['total']}"
    return results


def get_status() -> dict:
    """Return current Real-ESRGAN stack status."""
    ready = is_ready()
    model_ok = MODEL_FILE.exists() and MODEL_FILE.stat().st_size > 1_000_000 if MODEL_FILE.exists() else False
    return {
        "venv": "ready" if VENV_PYTHON.exists() else "missing",
        "dependencies": "installed" if ready else "not_installed",
        "model": "downloaded" if model_ok else "missing",
        "model_path": str(MODEL_FILE),
        "output_dir": str(OUTPUT_DIR),
        "install_cmd": f"bash '{ESRGAN_DIR}/install_esrgan.sh'",
    }


def _log_job(input_path: str, output_path: str, scale: int):
    """Append upscale job to daily log."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOGS_DIR / f"esrgan_{today}.jsonl"
        entry = {
            "ts": datetime.now().isoformat(),
            "input": input_path,
            "output": output_path,
            "scale": scale,
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

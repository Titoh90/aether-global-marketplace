"""
applio_executor.py — Applio voice cloning/conversion for IMPERIO Operator
Clones voices and converts audio to any trained voice (replaces ElevenLabs).

Usage from gateway:
  /voice_clone input.wav --model my_voice.pth          → convert audio
  /voice_start                                          → launch Applio web UI
  /voice_status                                         → check status

Fiverr use case:
  - Customer sends voice recording + target voice model
  - Run voice conversion → deliver output in 5 minutes
  - Price: $15-50 per clip

Requirements: venv installed in APPLIO/venv
"""

import subprocess
import logging
import json
from pathlib import Path
from datetime import datetime

log = logging.getLogger("applio_executor")

APPLIO_DIR  = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/APPLIO")
VENV_PYTHON = APPLIO_DIR / "venv/bin/python"
LOGS_DIR    = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator/logs/applio")
OUTPUT_DIR  = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE/voice_clones")
MODELS_DIR  = APPLIO_DIR / "logs"  # Applio stores models in logs/


_applio_proc = None  # Track web UI process


def is_ready() -> bool:
    """Check if Applio venv is functional."""
    if not VENV_PYTHON.exists():
        return False
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", "import torch; import numpy; print('ok')"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0 and "ok" in result.stdout
    except Exception:
        return False


def start_web_ui(port: int = 7865) -> dict:
    """
    Launch Applio Gradio web UI on given port.
    Returns immediately — UI runs in background.
    URL: http://localhost:{port}
    """
    global _applio_proc
    if _applio_proc and _applio_proc.poll() is None:
        return {"status": "already_running", "url": f"http://localhost:{port}"}

    if not is_ready():
        return {"status": "failed", "error": "Applio not installed. Run: install_applio.sh"}

    cmd = [str(VENV_PYTHON), str(APPLIO_DIR / "app.py"), "--port", str(port)]
    _applio_proc = subprocess.Popen(
        cmd,
        cwd=str(APPLIO_DIR),
        env={
            **__import__("os").environ,
            "PYTORCH_ENABLE_MPS_FALLBACK": "1",
            "PYTORCH_MPS_HIGH_WATERMARK_RATIO": "0.0",
        }
    )
    log.info(f"Applio UI started PID {_applio_proc.pid} → http://localhost:{port}")
    return {
        "status": "started",
        "pid": _applio_proc.pid,
        "url": f"http://localhost:{port}",
        "note": "First load takes ~30s. Use web UI to train + convert voices.",
    }


def stop_web_ui() -> dict:
    """Stop Applio web UI."""
    global _applio_proc
    if _applio_proc and _applio_proc.poll() is None:
        _applio_proc.terminate()
        _applio_proc = None
        return {"status": "stopped"}
    return {"status": "not_running"}


def voice_convert(input_audio: str, model_name: str = "my_voice",
                  pitch_shift: int = 0, output_name: str = None) -> dict:
    """
    Convert voice in audio file to trained voice model.

    Args:
        input_audio: Path to source audio (.wav, .mp3)
        model_name: Name of trained model in APPLIO/logs/{model_name}/
        pitch_shift: Semitones to shift (0 = no change, -12 = octave down)
        output_name: Output filename (auto if None)

    Returns:
        {"status": "success", "output": "/path/to/converted.wav"}

    Note: Model must be trained first via Applio web UI.
    For Fiverr voice cloning: customer provides voice samples → train model → convert.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    input_path = Path(input_audio)
    if not input_path.exists():
        return {"status": "failed", "error": f"Input not found: {input_audio}"}

    model_dir = MODELS_DIR / model_name
    if not model_dir.exists():
        return {
            "status": "failed",
            "error": f"Model '{model_name}' not found. Train it first in Applio UI at http://localhost:7865",
            "models_dir": str(MODELS_DIR),
        }

    pth_files = list(model_dir.glob("*.pth"))
    if not pth_files:
        return {"status": "failed", "error": f"No .pth model file in {model_dir}"}
    pth_file = pth_files[0]

    index_files = list(model_dir.glob("*.index"))
    index_file = index_files[0] if index_files else None

    if output_name is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"voice_{model_name}_{ts}.wav"
    out_path = OUTPUT_DIR / output_name

    # Use Applio's core RVC inference directly
    convert_script = f"""
import sys, os
sys.path.insert(0, "{APPLIO_DIR}")
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"

from rvc.infer.infer import VoiceConverter
vc = VoiceConverter()
vc.convert_audio(
    audio_input_path="{input_path}",
    audio_output_path="{out_path}",
    model_path="{pth_file}",
    index_path="{index_file or ''}",
    pitch=int({pitch_shift}),
    filter_radius=3,
    index_rate=0.75,
    volume_envelope=1,
    protect=0.5,
    hop_length=128,
    f0_method="rmvpe",
    split_audio=False,
    f0_autotune=False,
    clean_audio=True,
    clean_strength=0.7,
    export_format="WAV",
    upscale_audio=False,
)
print(f"Converted: {out_path}")
"""
    script_path = OUTPUT_DIR / "_convert_tmp.py"
    script_path.write_text(convert_script)

    try:
        result = subprocess.run(
            [str(VENV_PYTHON), str(script_path)],
            capture_output=True, text=True, timeout=300,
            cwd=str(APPLIO_DIR),
            env={
                **__import__("os").environ,
                "PYTORCH_ENABLE_MPS_FALLBACK": "1",
                "PYTORCH_MPS_HIGH_WATERMARK_RATIO": "0.0",
            }
        )
        script_path.unlink(missing_ok=True)
        if result.returncode != 0:
            return {"status": "failed", "error": result.stderr[-800:]}
        if not out_path.exists():
            return {"status": "failed", "error": "Output not created"}

        _log_job(str(input_path), str(out_path), model_name)
        return {"status": "success", "input": str(input_path),
                "output": str(out_path), "model": model_name}
    except subprocess.TimeoutExpired:
        script_path.unlink(missing_ok=True)
        return {"status": "failed", "error": "Timeout after 5 minutes"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def list_models() -> list:
    """List available trained voice models."""
    if not MODELS_DIR.exists():
        return []
    return [d.name for d in MODELS_DIR.iterdir()
            if d.is_dir() and list(d.glob("*.pth"))]


def get_status() -> dict:
    global _applio_proc
    running = _applio_proc and _applio_proc.poll() is None
    return {
        "venv": "ready" if VENV_PYTHON.exists() else "missing",
        "dependencies": "installed" if is_ready() else "not_installed",
        "web_ui": "running" if running else "stopped",
        "web_url": "http://localhost:7865" if running else None,
        "models": list_models(),
        "models_dir": str(MODELS_DIR),
        "output_dir": str(OUTPUT_DIR),
        "launch_cmd": "/voice_start",
    }


def _log_job(input_path: str, output: str, model: str):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOGS_DIR / f"applio_{today}.jsonl"
        entry = {"ts": datetime.now().isoformat(), "input": input_path,
                 "output": output, "model": model}
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

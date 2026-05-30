"""
stable_audio_executor.py — Stable Audio 2.0 music generation for IMPERIO
Generates background music for product videos (replaces royalty-free music sites).

Usage from gateway:
  /music "upbeat product demo 30 seconds"
  /music "cinematic dramatic 15s" --output my_video_bg.wav

Requirements: stable_audio_tools installed in STABLE_AUDIO/venv
Model: stability-ai/stable-audio-open-1.0 (HuggingFace, free)
"""

import subprocess
import logging
import json
from pathlib import Path
from datetime import datetime

log = logging.getLogger("stable_audio_executor")

STABLE_DIR  = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/STABLE_AUDIO")
VENV_PYTHON = STABLE_DIR / "venv/bin/python"
MODELS_DIR  = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/STABLE_AUDIO/models")
LOGS_DIR    = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator/logs/stable_audio")
OUTPUT_DIR  = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE/audio")

# HuggingFace model (free, no API key needed for open weights)
HF_MODEL_ID = "stabilityai/stable-audio-open-1.0"


def is_ready() -> bool:
    """Check if stable_audio_tools is installed."""
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), "-c", "import stable_audio_tools; print('ok')"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0 and "ok" in result.stdout
    except Exception:
        return False


def generate_music(prompt: str, duration: float = 30.0,
                   output_name: str = None, cfg_scale: float = 6.0) -> dict:
    """
    Generate background music using Stable Audio 2.0.

    Args:
        prompt: Music description ("upbeat product ad, 120bpm, electronic")
        duration: Length in seconds (default 30)
        output_name: Output filename (auto-generated if None)
        cfg_scale: Classifier-free guidance (6.0 = balanced quality/creativity)

    Returns:
        {"status": "success", "output": "/path/to/music.wav", "duration": 30.0}

    NOTE: First run downloads ~1.5GB model from HuggingFace (cached after first use).
    Set HF_TOKEN env var if you have a HuggingFace account (not required for open weights).
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not is_ready():
        return {"status": "failed", "error": "stable_audio_tools not installed. Run: setup_stable_audio.sh"}

    if output_name is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"music_{ts}.wav"

    out_path = OUTPUT_DIR / output_name

    # Python script to run inside the venv
    gen_script = f"""
import torch
from stable_audio_tools import get_pretrained_model
from stable_audio_tools.inference.generation import generate_diffusion_cond
from stable_audio_tools.models.utils import load_ckpt_state_dict
import torchaudio

device = "mps" if torch.backends.mps.is_available() else "cpu"
print(f"Using device: {{device}}")

model, model_config = get_pretrained_model("{HF_MODEL_ID}")
sample_rate = model_config["sample_rate"]
sample_size = model_config["sample_size"]
model = model.to(device)

conditioning = [{{
    "prompt": {json.dumps(prompt)},
    "seconds_start": 0,
    "seconds_total": {duration},
}}]

output = generate_diffusion_cond(
    model,
    steps=100,
    cfg_scale={cfg_scale},
    conditioning=conditioning,
    sample_size=sample_size,
    sigma_min=0.3,
    sigma_max=500,
    sampler_type="dpmpp-3m-sde",
    device=device,
)

# Trim to expected duration
output = output[:, :, :int(sample_rate * {duration})]
output = output.cpu().squeeze()
torchaudio.save("{out_path}", output.unsqueeze(0), sample_rate)
print(f"Saved: {out_path}")
"""

    script_path = OUTPUT_DIR / "_gen_tmp.py"
    script_path.write_text(gen_script)

    try:
        log.info(f"Generating music: {prompt[:60]} ({duration}s)")
        result = subprocess.run(
            [str(VENV_PYTHON), str(script_path)],
            capture_output=True, text=True, timeout=600,
            env={**__import__("os").environ, "PYTORCH_ENABLE_MPS_FALLBACK": "1"}
        )
        script_path.unlink(missing_ok=True)

        if result.returncode != 0:
            return {"status": "failed", "error": result.stderr[-800:]}

        if not out_path.exists():
            return {"status": "failed", "error": "Output file not created"}

        _log_job(prompt, str(out_path), duration)
        return {
            "status": "success",
            "output": str(out_path),
            "duration": duration,
            "prompt": prompt,
        }
    except subprocess.TimeoutExpired:
        script_path.unlink(missing_ok=True)
        return {"status": "failed", "error": "Timeout after 10 minutes"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def generate_video_soundtrack(video_style: str = "product ad",
                               duration: float = 30.0) -> dict:
    """
    Pre-built soundtrack generator for product videos.
    video_style: "product ad" | "tiktok viral" | "dramatic" | "chill"
    """
    style_prompts = {
        "product ad":    "upbeat corporate advertisement music, 120bpm, modern electronic, professional",
        "tiktok viral":  "viral TikTok trending beat, catchy hook, energetic, young audience",
        "dramatic":      "cinematic dramatic score, orchestral tension, build-up, epic",
        "chill":         "lo-fi chill beats, relaxed, background music, 80bpm, ambient",
    }
    prompt = style_prompts.get(video_style, style_prompts["product ad"])
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return generate_music(prompt, duration, f"soundtrack_{video_style}_{ts}.wav")


def get_status() -> dict:
    ready = is_ready()
    return {
        "venv": "ready" if VENV_PYTHON.exists() else "missing",
        "dependencies": "installed" if ready else "not_installed",
        "model": HF_MODEL_ID,
        "model_note": "~1.5GB download on first use (cached to HuggingFace cache)",
        "device": "mps (Apple Silicon)",
        "output_dir": str(OUTPUT_DIR),
    }


def _log_job(prompt: str, output: str, duration: float):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = LOGS_DIR / f"stable_audio_{today}.jsonl"
        entry = {"ts": datetime.now().isoformat(), "prompt": prompt[:200],
                 "output": output, "duration": duration}
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

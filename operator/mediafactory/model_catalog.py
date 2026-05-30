"""
model_catalog.py — Live model catalog for OpenRouter + NVIDIA NIM

Fetches available text-generation models from both providers daily.
Caches to disk so each pipeline call doesn't hit the API.

Usage:
    from mediafactory.model_catalog import get_optimizer_models, get_nvidia_models
    models = get_optimizer_models()   # → ["meta-llama/llama-3.3-70b-instruct:free", ...]
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from pathlib import Path
from typing import Sequence

log = logging.getLogger("model_catalog")

_CACHE_DIR = Path.home() / ".cache" / "imperio" / "model_catalog"
_CACHE_TTL = 86400  # 24 hours
_ENV_FILES = (
    Path(__file__).resolve().parents[3] / "SYSTEM_FILES" / "SECURE_CREDENTIALS" / "IMPERIO_NUCLEO.env",
    Path.home() / "IMPERIO_NUCLEO" / ".env",
)

# ── Hardcoded fallbacks (used when APIs unreachable) ──────────────────────────

_FALLBACK_OPENROUTER = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "deepseek/deepseek-v4-flash:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "google/gemma-4-26b-a4b-it:free",
]

_FALLBACK_NVIDIA = [
    "meta/llama-3.1-8b-instruct",       # confirmed 200
    "deepseek-ai/deepseek-v4-flash",    # confirmed 200
    "google/gemma-2-2b-it",             # confirmed 200 (small, fast)
]

# Reasoning/vision/code models — bad for JSON output tasks
_SKIP_PATTERNS = (
    "thinking", "reasoning", ":r1", "-r1", "-r2", "trinity",
    "laguna", "nemotron-3-nano-omni", "fuyu", "clip", "deplot",
    "recurrentgemma", "starcoder", "codellama", "codegemma",
    "granite-8b-code", "granite-34b-code", "sea-lion",
    "rerank", "embed", "bge-",
)

# ── Key loading ───────────────────────────────────────────────────────────────

def _load_key(names: Sequence[str]) -> str | None:
    for env_file in _ENV_FILES:
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            for name in names:
                if line.strip().startswith(f"{name}="):
                    return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    for name in names:
        val = os.environ.get(name)
        if val:
            return val
    return None


def _openrouter_key() -> str | None:
    return _load_key(["OPENROUTER_API_KEY"])


def _nvidia_key() -> str | None:
    return _load_key(["NVIDIA_NIM_API_KEY", "NVIDIA_API_KEY"])

# ── Cache helpers ─────────────────────────────────────────────────────────────

def _cache_path(provider: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{provider}.json"


def _cache_valid(path: Path) -> bool:
    return path.exists() and (time.time() - path.stat().st_mtime) < _CACHE_TTL


def _load_cache(provider: str) -> list[str] | None:
    p = _cache_path(provider)
    if _cache_valid(p):
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return None


def _save_cache(provider: str, models: list[str]) -> None:
    try:
        _cache_path(provider).write_text(json.dumps(models))
    except Exception as e:
        log.warning(f"Cache write failed: {e}")

# ── Model scoring ─────────────────────────────────────────────────────────────

def _is_good_text_model(model_id: str) -> bool:
    return not any(pat in model_id.lower() for pat in _SKIP_PATTERNS)


def _model_priority(model_id: str) -> int:
    """Higher = better for general instruction/JSON tasks."""
    score = 0
    m = model_id.lower()
    if any(x in m for x in ("instruct", "-it", "chat")):
        score += 30
    for size, pts in (("70b", 20), ("72b", 20), ("120b", 22), ("405b", 25),
                      ("236b", 18), ("30b", 12), ("32b", 12), ("36b", 12),
                      ("12b", 8), ("8b", 5), ("9b", 5)):
        if size in m:
            score += pts
            break
    if any(x in m for x in ("llama-3.3", "llama-3.1", "gemma-4", "gemma-3",
                             "deepseek-v4", "mistral-7b-instruct")):
        score += 15
    return score

# ── Fetch logic ───────────────────────────────────────────────────────────────

def _fetch_openrouter() -> list[str]:
    key = _openrouter_key()
    if not key:
        return _FALLBACK_OPENROUTER

    cached = _load_cache("openrouter")
    if cached is not None:
        log.debug(f"OpenRouter catalog: {len(cached)} models (cached)")
        return cached

    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        models = [
            m["id"] for m in data.get("data", [])
            if ":free" in m["id"]
            and m.get("architecture", {}).get("modality", "") == "text->text"
            and _is_good_text_model(m["id"])
        ]
        models.sort(key=lambda m: -_model_priority(m))
        log.info(f"OpenRouter catalog refreshed: {len(models)} free text models")
        _save_cache("openrouter", models)
        return models or _FALLBACK_OPENROUTER

    except Exception as e:
        log.warning(f"OpenRouter fetch failed: {e}")
        return _FALLBACK_OPENROUTER


def _fetch_nvidia() -> list[str]:
    key = _nvidia_key()
    if not key:
        return _FALLBACK_NVIDIA

    cached = _load_cache("nvidia")
    if cached is not None:
        log.debug(f"NVIDIA catalog: {len(cached)} models (cached)")
        return cached

    try:
        req = urllib.request.Request(
            "https://integrate.api.nvidia.com/v1/models?limit=200",
            headers={"Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())

        models = [
            m["id"] for m in data.get("data", [])
            if _is_good_text_model(m["id"])
        ]
        models.sort(key=lambda m: -_model_priority(m))
        log.info(f"NVIDIA catalog refreshed: {len(models)} text models")
        _save_cache("nvidia", models)
        return models or _FALLBACK_NVIDIA

    except Exception as e:
        log.warning(f"NVIDIA fetch failed: {e}")
        return _FALLBACK_NVIDIA

# ── Public API ────────────────────────────────────────────────────────────────

def get_optimizer_models(max_each: int = 3) -> list[str]:
    """
    Best models for prompt optimization tasks.
    Interleaves OpenRouter free + NVIDIA for maximum availability.
    Pattern: [OR1, NV1, OR2, NV2, OR3, NV3]
    """
    or_models = _fetch_openrouter()[:max_each]
    nv_models = [f"nvidia::{m}" for m in _fetch_nvidia()[:max_each]]
    combined: list[str] = []
    for pair in zip(or_models, nv_models):
        combined.extend(pair)
    # append leftovers
    combined.extend(or_models[len(nv_models):])
    combined.extend(nv_models[len(or_models):])
    return combined


def get_nvidia_models(max_models: int = 5) -> list[str]:
    return _fetch_nvidia()[:max_models]


def get_openrouter_models(max_models: int = 5) -> list[str]:
    return _fetch_openrouter()[:max_models]


def refresh_all(force: bool = False) -> dict[str, int]:
    """Force-refresh both catalogs. Returns model counts."""
    if force:
        _cache_path("openrouter").unlink(missing_ok=True)
        _cache_path("nvidia").unlink(missing_ok=True)
    return {
        "openrouter": len(_fetch_openrouter()),
        "nvidia": len(_fetch_nvidia()),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    counts = refresh_all(force=True)
    print(f"\nOpenRouter free text models: {counts['openrouter']}")
    print(f"NVIDIA text models:          {counts['nvidia']}")
    print("\nBest optimizer models (interleaved):")
    for m in get_optimizer_models():
        print(f"  {m}")

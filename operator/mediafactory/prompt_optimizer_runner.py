"""
prompt_optimizer_runner.py — OptimizerRunner implementation via OpenRouter

Calls OpenRouter with a structured meta-prompt (inspired by prompt-optimizer
templates) to improve user video requests before sending to Pixelle.

Returns a dict with:
  optimized_prompt, platform, format, goal

Designed to be passed as optimizer_runner= to optimize_user_request().
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

log = logging.getLogger("prompt_optimizer_runner")

_ENV_FILES = (
    Path(__file__).resolve().parents[3] / "SYSTEM_FILES" / "SECURE_CREDENTIALS" / "IMPERIO_NUCLEO.env",
    Path.home() / "IMPERIO_NUCLEO" / ".env",
)

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
_NVIDIA_BASE_URL     = "https://integrate.api.nvidia.com/v1"

# Loaded lazily from model_catalog (fetches OR + NVIDIA, cached 24h)
_OPTIMIZATION_MODELS: list[str] | None = None


def _get_models() -> list[str]:
    global _OPTIMIZATION_MODELS
    if _OPTIMIZATION_MODELS is None:
        try:
            from mediafactory.model_catalog import get_optimizer_models
            _OPTIMIZATION_MODELS = get_optimizer_models(max_each=3)
            log.info(f"Model catalog loaded: {_OPTIMIZATION_MODELS}")
        except Exception as e:
            log.warning(f"Model catalog unavailable ({e}) — using hardcoded fallback")
            _OPTIMIZATION_MODELS = [
                "meta-llama/llama-3.3-70b-instruct:free",
                "nvidia::meta/llama-3.3-70b-instruct",
                "deepseek/deepseek-v4-flash:free",
                "nvidia::google/gemma-3-12b-it",
            ]
    return _OPTIMIZATION_MODELS

_META_PROMPT = """\
You are a social media video prompt specialist. Your job is to transform a rough
user request into a clear, structured video production prompt optimized for
short-form content (TikTok / Instagram Reels / YouTube Shorts).

Analyze the user request and output ONLY valid JSON — no explanation, no markdown:

{{
  "optimized_prompt": "<concise production prompt: hook → problem → solution → CTA, max 2 sentences>",
  "platform": "<tiktok|instagram|youtube>",
  "format": "<short|story|reel>",
  "goal": "<awareness|conversion|engagement>"
}}

Rules:
- optimized_prompt must be in English, max 60 words
- Start with the strongest visual hook
- Include the core benefit and one concrete CTA
- No hashtags, no emojis, no filler

User request: {user_request}
"""


def _load_openrouter_key() -> str | None:
    for env_file in _ENV_FILES:
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("OPENROUTER_API_KEY="):
                return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("OPENROUTER_API_KEY")


def _call_llm(prompt: str, model: str) -> str:
    """
    Calls OpenRouter or NVIDIA NIM depending on model prefix.
    NVIDIA models use prefix 'nvidia::' e.g. 'nvidia::meta/llama-3.3-70b-instruct'.
    """
    import urllib.request

    if model.startswith("nvidia::"):
        real_model = model[len("nvidia::"):]
        key = _load_openrouter_key.__func__() if False else _load_nvidia_key()
        base_url = _NVIDIA_BASE_URL
        headers_extra: dict = {}
    else:
        real_model = model
        key = _load_openrouter_key()
        base_url = _OPENROUTER_BASE_URL
        headers_extra = {
            "HTTP-Referer": "https://github.com/Imperio-Nucleo",
            "X-Title": "Imperio MediaFactory",
        }

    if not key:
        raise RuntimeError(f"No API key for model {model}")

    payload = json.dumps({
        "model": real_model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200,
        "temperature": 0.3,
    }).encode()

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            **headers_extra,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read())

    content = (body.get("choices") or [{}])[0].get("message", {}).get("content")
    if not content:
        raise ValueError(f"Empty content in response from {model}")
    return content


def _load_nvidia_key() -> str | None:
    for env_file in _ENV_FILES:
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            for name in ("NVIDIA_NIM_API_KEY", "NVIDIA_API_KEY"):
                if line.strip().startswith(f"{name}="):
                    return line.strip().split("=", 1)[1].strip().strip('"').strip("'")


def run_optimizer(raw_input: str) -> dict:
    """
    OptimizerRunner callable — pass this to optimize_user_request().

    Returns dict: {optimized_prompt, platform, format, goal}
    Raises on total failure (caller falls back to static prompt).
    """
    prompt = _META_PROMPT.format(user_request=raw_input)
    last_error: Exception | None = None

    for model in _get_models():
        try:
            log.info(f"Optimizing prompt via {model}...")
            raw_response = _call_llm(prompt, model)

            # Extract JSON from response (model may wrap in markdown)
            start = raw_response.find("{")
            end = raw_response.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError(f"No JSON in response: {raw_response[:200]}")

            result = json.loads(raw_response[start:end])

            required = {"optimized_prompt", "platform", "format", "goal"}
            if not required.issubset(result.keys()):
                raise ValueError(f"Missing keys in response: {result.keys()}")

            log.info(f"Prompt optimized via {model}: {result['optimized_prompt'][:60]}...")
            return result

        except Exception as exc:
            log.warning(f"Model {model} failed: {exc}")
            last_error = exc
            time.sleep(2)  # brief pause before trying next model
            continue

    raise RuntimeError(f"All optimization models failed. Last: {last_error}")

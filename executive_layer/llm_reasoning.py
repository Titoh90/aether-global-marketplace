"""
llm_reasoning.py — LLM-powered reasoning for HERMES executive agent.

Uses FREE APIs only:
1. OpenRouter free models (Llama 3.1 8B, Gemma, etc.)
2. Ollama local (Qwen 2.5)
3. NVIDIA NIM free tier (if available)

Fallback chain ensures 24/7 availability.
"""

from __future__ import annotations

import json
import os
import logging
from pathlib import Path

import httpx

log = logging.getLogger("hermes.reasoning")

# Free model priorities
OPENROUTER_FREE_MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "deepseek/deepseek-v4-flash:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "openai/gpt-oss-20b:free",
]

OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5:7b"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def reason(
    prompt: str,
    system_prompt: str = "",
    max_tokens: int = 500,
    temperature: float = 0.3,
) -> str:
    """
    Generate LLM response using free API fallback chain.

    Order: OpenRouter free → Ollama local → simple template
    """
    # 1. Try OpenRouter free models
    api_key = os.environ.get("OPENROUTER_API_KEY") or _get_key_from_launchctl("OPENROUTER_API_KEY")
    if api_key:
        for model in OPENROUTER_FREE_MODELS:
            try:
                result = await _call_openrouter(api_key, model, prompt, system_prompt, max_tokens, temperature)
                if result:
                    log.info(f"Reasoning via OpenRouter/{model}")
                    return result
            except Exception as e:
                log.debug(f"OpenRouter {model} failed: {e}")
                continue

    # 2. Try Ollama local
    try:
        result = await _call_ollama(prompt, system_prompt, max_tokens, temperature)
        if result:
            log.info("Reasoning via Ollama local")
            return result
    except Exception as e:
        log.debug(f"Ollama failed: {e}")

    # 3. Fallback — return raw data without LLM formatting
    log.warning("All LLM providers unavailable — returning unformatted response")
    return prompt  # return the data as-is


async def _call_openrouter(
    api_key: str,
    model: str,
    prompt: str,
    system_prompt: str,
    max_tokens: int,
    temperature: float,
) -> str | None:
    """Call OpenRouter free model."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            return None
        return choices[0].get("message", {}).get("content", "")


async def _call_ollama(
    prompt: str,
    system_prompt: str,
    max_tokens: int,
    temperature: float,
) -> str | None:
    """Call local Ollama."""
    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            },
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("response", "")


def _get_key_from_launchctl(key_name: str) -> str:
    """Try to get API key from launchctl (macOS)."""
    try:
        import subprocess
        result = subprocess.run(
            ["launchctl", "getenv", key_name],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""

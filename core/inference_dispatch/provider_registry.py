#!/usr/bin/env python3
"""
provider_registry.py — Provider registration and key discovery.

PROVIDERS is a MappingProxyType (frozen at import time).
Runtime key availability checked via os.environ at call time (supports launchctl).
"""

from __future__ import annotations

import os
import subprocess
from types import MappingProxyType

from core.inference_dispatch.schemas import ProviderStatus

# ── Provider definitions ──────────────────────────────────────────────────────
# key_env: environment variable name for API key (None = always available)
# base_url: OpenAI-compat base URL or "direct" for SDK-only
# models: default model list for this provider (first = preferred)

_PROVIDER_DEFS: dict[str, dict] = {
    "groq": {
        "key_env":  "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "models":   ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"],
    },
    "gemini": {
        "key_env":  "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models":   ["gemini-2.0-flash", "gemini-1.5-flash"],
    },
    "anthropic": {
        "key_env":  "ANTHROPIC_API_KEY",
        "base_url": "direct",
        "models":   ["claude-haiku-4-5-20251001", "claude-sonnet-4-6"],
    },
    "openrouter": {
        "key_env":  "OPENROUTER_API_KEY",
        "base_url": "https://openrouter.ai/api/v1",
        "models":   ["meta-llama/llama-3.1-8b-instruct:free", "google/gemini-flash-1.5"],
    },
    "github_models": {
        "key_env":  "GITHUB_TOKEN",
        "base_url": "https://models.inference.ai.azure.com",
        "models":   ["gpt-4o-mini", "Phi-3.5-mini-instruct"],
    },
    "freellmapi": {
        "key_env":  "FREELLMAPI_KEY",  # optional — server may accept no-key
        "base_url": "http://localhost:3001",
        "models":   ["auto"],
    },
    "local": {
        "key_env":  None,  # always available
        "base_url": "local",
        "models":   ["all-MiniLM-L6-v2"],
    },
}

# Freeze the registry — no runtime mutation
PROVIDERS: MappingProxyType = MappingProxyType(_PROVIDER_DEFS)


# ── Key discovery ─────────────────────────────────────────────────────────────

def _get_key(key_env: str | None) -> str:
    """
    Resolve API key: check os.environ first, then launchctl (macOS).
    Returns "" if not found.
    """
    if key_env is None:
        return "present"  # sentinel for always-available providers

    val = os.environ.get(key_env, "")
    if val:
        return val

    # macOS launchctl fallback
    try:
        result = subprocess.run(
            ["launchctl", "getenv", key_env],
            capture_output=True, text=True, timeout=2,
        )
        val = result.stdout.strip()
        if val:
            return val
    except Exception:
        pass

    return ""


# ── Public API ────────────────────────────────────────────────────────────────

def is_available(provider_id: str) -> ProviderStatus:
    """
    Check if a provider has its API key set AND is not in health cooldown.

    Imports provider_health lazily to avoid circular imports.
    """
    if provider_id not in PROVIDERS:
        return ProviderStatus(provider_id=provider_id, available=False, reason="unknown")

    key_env = PROVIDERS[provider_id]["key_env"]
    key_val = _get_key(key_env)

    if not key_val:
        return ProviderStatus(provider_id=provider_id, available=False, reason="no_key")

    # Check health (lazy import)
    try:
        from core.inference_dispatch import provider_health as ph
        if not ph.is_healthy(provider_id):
            return ProviderStatus(provider_id=provider_id, available=False, reason="unhealthy")
    except ImportError:
        pass

    return ProviderStatus(provider_id=provider_id, available=True, reason="ok")


def get_available_providers() -> list[str]:
    """Return list of provider IDs that are currently available (key present + healthy)."""
    return [pid for pid in PROVIDERS if is_available(pid).available]


def get_models(provider_id: str) -> list[str]:
    """Return model list for a provider."""
    return list(PROVIDERS.get(provider_id, {}).get("models", []))


def get_base_url(provider_id: str) -> str:
    """Return base URL for a provider."""
    return PROVIDERS.get(provider_id, {}).get("base_url", "")


def get_api_key(provider_id: str) -> str:
    """Return resolved API key for a provider. Returns '' if not available."""
    key_env = PROVIDERS.get(provider_id, {}).get("key_env")
    if key_env is None:
        return ""
    return _get_key(key_env)

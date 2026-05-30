#!/usr/bin/env python3
"""
openai_compat_client.py — Minimal stdlib HTTP client for OpenAI-compatible endpoints.

No openai SDK, no anthropic SDK — pure urllib.request + json.
Targets freellmapi (or any OpenAI-compat endpoint) at FREELLMAPI_URL.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

# Default: freellmapi production server
_DEFAULT_BASE = "http://localhost:3001"


class ProviderError(Exception):
    """Raised when the provider returns an error response."""
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status


def _base_url() -> str:
    return os.environ.get("FREELLMAPI_URL", _DEFAULT_BASE).rstrip("/")


def _api_key() -> str:
    return os.environ.get("FREELLMAPI_KEY", "")


def complete(
    model: str,
    messages: list[dict],
    max_tokens: int = 512,
    timeout: int = 30,
    stream: bool = False,
) -> str:
    """
    Send chat completion request. Returns response text string.

    Raises ProviderError on HTTP errors or malformed responses.
    """
    url = f"{_base_url()}/v1/chat/completions"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": stream,
    }

    body = json.dumps(payload).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    key = _api_key()
    if key:
        headers["Authorization"] = f"Bearer {key}"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode(errors="replace")[:200]
        except Exception:
            pass
        raise ProviderError(f"HTTP {e.code}: {body_text}", status=e.code) from e
    except Exception as e:
        raise ProviderError(f"Request failed: {e}") from e

    if stream:
        # Parse SSE stream — collect all data lines and extract content
        text_parts = []
        for line in raw.decode(errors="replace").splitlines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                if delta.get("content"):
                    text_parts.append(delta["content"])
            except Exception:
                continue
        return "".join(text_parts)

    # Non-streaming: parse JSON response
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProviderError(f"Invalid JSON response: {e}") from e

    if "error" in data:
        raise ProviderError(f"Provider error: {data['error']}")

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ProviderError(f"Unexpected response shape: {e} — {str(data)[:200]}") from e

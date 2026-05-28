#!/usr/bin/env python3
"""
test_freellmapi.py — Validate freellmapi server compatibility.

Requires: freellmapi server running on localhost:3001
Run:  python3 tests/test_freellmapi.py

When run via pytest without a running server, network-dependent tests
are skipped gracefully (pytest.skip) instead of failing.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = os.environ.get("FREELLMAPI_URL", "http://localhost:3001")
API_KEY  = os.environ.get("FREELLMAPI_KEY", "")

_PASS = 0
_FAIL = 0


def _server_is_reachable() -> bool:
    """Check if the FreeLLM API server is reachable. Never raises."""
    try:
        req = urllib.request.Request(f"{BASE_URL}/v1/models")
        if API_KEY:
            req.add_header("Authorization", f"Bearer {API_KEY}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def _require_server() -> None:
    """Skip the current test if the FreeLLM API server is unreachable."""
    if not _server_is_reachable():
        pytest.skip(f"FreeLLM API server not reachable at {BASE_URL}")


def _check(name: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  ✅ {name}")
    else:
        _FAIL += 1
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


def _post(path: str, payload: dict, timeout: int = 30) -> tuple[int, dict | str]:
    """POST JSON to freellmapi. Returns (status, response)."""
    url = f"{BASE_URL}{path}"
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw.decode(errors="replace")
    except urllib.error.HTTPError as e:
        body_txt = e.read().decode(errors="replace")[:300]
        try:
            return e.code, json.loads(body_txt)
        except Exception:
            return e.code, body_txt


def test_server_reachable() -> None:
    """Verify the FreeLLM API server is reachable."""
    print("\n[1] Server reachability")
    if not _server_is_reachable():
        print(f"\n  ⚠️  freellmapi not running at {BASE_URL}. Start with:")
        print(f"     cd /Volumes/OPENCLAW_STORAG\\ 1/IMPERIO_ROOT/vendor/freellmapi")
        print(f"     node server/dist/index.js")
        pytest.skip(f"FreeLLM API server not reachable at {BASE_URL}")

    req = urllib.request.Request(f"{BASE_URL}/v1/models")
    if API_KEY:
        req.add_header("Authorization", f"Bearer {API_KEY}")
    with urllib.request.urlopen(req, timeout=5) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        data = json.loads(resp.read())
        assert "data" in data, "Response missing 'data' key"


def test_basic_completion() -> None:
    _require_server()
    print("\n[2] Basic completion (non-streaming)")
    t0 = time.time()
    status, resp = _post("/v1/chat/completions", {
        "model": "auto",
        "messages": [{"role": "user", "content": "Reply with exactly: HELLO"}],
        "max_tokens": 20,
        "stream": False,
    })
    latency_ms = int((time.time() - t0) * 1000)

    _check("HTTP 200", status == 200, f"got {status}")
    if isinstance(resp, dict):
        _check("Has 'choices'", "choices" in resp, str(resp)[:100])
        if "choices" in resp and resp["choices"]:
            content = resp["choices"][0].get("message", {}).get("content", "")
            _check("Content non-empty", bool(content), repr(content))
            model_used = resp.get("model", "unknown")
            provider   = resp.get("x-routed-via", resp.get("system_fingerprint", "?"))
            print(f"     model={model_used}  provider={provider}  latency={latency_ms}ms")
    else:
        _check("Valid JSON response", False, str(resp)[:100])


def test_streaming() -> None:
    _require_server()
    print("\n[3] Streaming (stream=True)")
    url = f"{BASE_URL}/v1/chat/completions"
    payload = {
        "model": "auto",
        "messages": [{"role": "user", "content": "Count to 3, one number per word."}],
        "max_tokens": 30,
        "stream": True,
    }
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode(errors="replace")
        latency_ms = int((time.time() - t0) * 1000)

        chunks = [l for l in raw.splitlines() if l.startswith("data:")]
        _check("SSE chunks received", len(chunks) > 0, f"{len(chunks)} lines")
        _check("[DONE] marker present", "data: [DONE]" in raw)

        # Extract content
        parts = []
        for line in chunks:
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                d = json.loads(data)
                c = d.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if c:
                    parts.append(c)
            except Exception:
                pass
        assembled = "".join(parts)
        _check("Content assembled from stream", bool(assembled), repr(assembled[:50]))
        print(f"     assembled='{assembled[:60]}'  latency={latency_ms}ms")

    except Exception as e:
        _check("Stream request succeeded", False, str(e))


def test_json_schema() -> None:
    _require_server()
    print("\n[4] OpenAI response schema compatibility")
    _, resp = _post("/v1/chat/completions", {
        "model": "auto",
        "messages": [{"role": "user", "content": "one"}],
        "max_tokens": 5,
    })
    if isinstance(resp, dict):
        _check("'id' field present",      "id" in resp)
        _check("'object' field present",  "object" in resp)
        _check("'choices' is list",       isinstance(resp.get("choices"), list))
        if resp.get("choices"):
            ch = resp["choices"][0]
            _check("choice has 'message'",    "message" in ch)
            _check("choice has 'finish_reason'", "finish_reason" in ch)
    else:
        _check("Valid dict response", False, str(resp)[:100])


if __name__ == "__main__":
    print(f"freellmapi validation — {BASE_URL}")
    print("=" * 50)

    if not _server_is_reachable():
        print(f"\nRESULT: SKIPPED — server not running at {BASE_URL}")
        sys.exit(0)

    test_basic_completion()
    test_streaming()
    test_json_schema()

    print(f"\n{'='*50}")
    print(f"RESULT: {_PASS} PASS  {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)

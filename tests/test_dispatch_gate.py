#!/usr/bin/env python3
"""
test_dispatch_gate.py — Guard rail enforcement tests.

Verifies that routing violations are caught at runtime, not silently swallowed.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from platform_dispatch.platform_registry import (
    Executor, get_executor, is_forbidden, PLATFORM_REGISTRY
)
from platform_dispatch.dispatch_gate import (
    DispatchGate, DispatchViolationError, UnregisteredPlatformError
)

_PASS = 0
_FAIL = 0


def _check(name: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        _PASS += 1
        print(f"  ✅ {name}")
    else:
        _FAIL += 1
        print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))


def _gate_with_stub() -> DispatchGate:
    """Fresh gate with stub executors registered."""
    gate = DispatchGate()
    gate.register_executor(Executor.COMPOSIO, lambda **kw: {"ok": True})
    gate.register_executor(Executor.CDP,      lambda **kw: {"ok": True})
    gate.register_executor(Executor.FLOW,     lambda **kw: {"ok": True})
    return gate


# ── Registry correctness ───────────────────────────────────────────────────────

def test_platform_routing() -> None:
    print("\n[1] Platform → Executor routing")
    cases = [
        ("twitter",   Executor.COMPOSIO),
        ("x",         Executor.COMPOSIO),
        ("pinterest",  Executor.COMPOSIO),
        ("facebook",  Executor.COMPOSIO),
        ("youtube",   Executor.COMPOSIO),
        ("tiktok",    Executor.CDP),
        ("instagram", Executor.CDP),
        ("flow",      Executor.FLOW),
        ("truth_layer", Executor.INTERNAL),
    ]
    for platform, expected in cases:
        got = get_executor(platform)
        _check(f"{platform} → {expected.value}", got == expected, f"got {got.value}")


def test_unknown_platform_raises() -> None:
    print("\n[2] Unknown platform raises KeyError")
    try:
        get_executor("myspace")
        _check("KeyError raised", False, "no exception")
    except KeyError:
        _check("KeyError raised", True)


# ── Forbidden routes ───────────────────────────────────────────────────────────

def test_forbidden_routes() -> None:
    print("\n[3] Forbidden routes detected")
    forbidden_cases = [
        ("mcp", "twitter"),
        ("mcp", "instagram"),
        ("mcp", "tiktok"),
        ("cdp", "twitter"),
        ("cdp", "facebook"),
        ("composio", "tiktok"),
        ("composio", "instagram"),
        ("composio", "flow"),
        ("cdp", "flow"),
    ]
    for caller, platform in forbidden_cases:
        _check(f"{caller}:{platform} is forbidden",
               is_forbidden(caller, platform))


def test_allowed_routes() -> None:
    print("\n[4] Allowed routes not blocked")
    allowed_cases = [
        ("social_poster", "twitter"),
        ("social_poster", "tiktok"),
        ("social_poster", "instagram"),
        ("master_pipeline", "facebook"),
    ]
    for caller, platform in allowed_cases:
        _check(f"{caller}:{platform} is NOT forbidden",
               not is_forbidden(caller, platform))


# ── Gate enforcement ───────────────────────────────────────────────────────────

def test_gate_blocks_mcp_posting() -> None:
    print("\n[5] Gate blocks MCP posting to social platforms")
    gate = _gate_with_stub()
    for platform in ["twitter", "instagram", "tiktok", "facebook", "pinterest"]:
        try:
            gate.route(platform=platform, action="post", params={}, caller="mcp")
            _check(f"mcp→{platform} blocked", False, "no exception raised")
        except DispatchViolationError:
            _check(f"mcp→{platform} blocked", True)


def test_gate_blocks_internal_dispatch() -> None:
    print("\n[6] Gate blocks external dispatch to INTERNAL platforms")
    gate = _gate_with_stub()
    for platform in ["truth_layer", "copy_engine", "master_pipeline"]:
        try:
            gate.route(platform=platform, action="post", params={}, caller="anything")
            _check(f"internal '{platform}' blocked", False, "no exception")
        except (DispatchViolationError, KeyError):
            _check(f"internal '{platform}' blocked", True)


def test_gate_allows_correct_routes() -> None:
    print("\n[7] Gate allows correct routes")
    gate = _gate_with_stub()

    # social_poster → twitter via Composio
    result = gate.route(platform="twitter", action="post", params={}, caller="social_poster")
    _check("social_poster→twitter allowed", result.success, result.error)
    _check("twitter uses COMPOSIO executor", result.executor == Executor.COMPOSIO)

    # social_poster → tiktok via CDP
    result = gate.route(platform="tiktok", action="post", params={}, caller="social_poster")
    _check("social_poster→tiktok allowed", result.success, result.error)
    _check("tiktok uses CDP executor", result.executor == Executor.CDP)


def test_gate_dry_run() -> None:
    print("\n[8] Dry run validates without executing")
    gate = _gate_with_stub()
    called = []
    gate.register_executor(Executor.COMPOSIO, lambda **kw: called.append(True))

    gate.route(platform="twitter", action="post", params={}, caller="test", dry_run=True)
    _check("Executor NOT called in dry_run", len(called) == 0)


def test_gate_unregistered_executor_raises() -> None:
    print("\n[9] Gate raises if executor not registered at startup")
    gate = DispatchGate()  # no executors registered
    try:
        gate.route(platform="twitter", action="post", params={}, caller="social_poster")
        _check("DispatchViolationError raised", False)
    except DispatchViolationError:
        _check("DispatchViolationError raised", True)


def test_capability_enforcement() -> None:
    print("\n[10] Gate rejects actions outside executor capability")
    gate = _gate_with_stub()
    # FLOW executor only supports generate_image / generate_video, not "post"
    try:
        gate.route(platform="flow", action="post", params={}, caller="anything")
        _check("FLOW:post blocked (capability)", False)
    except DispatchViolationError:
        _check("FLOW:post blocked (capability)", True)


def test_cdp_blocked_from_oauth_platforms() -> None:
    print("\n[11] CDP executor blocked from OAuth platforms")
    gate = _gate_with_stub()
    for platform in ["twitter", "facebook", "youtube", "pinterest"]:
        try:
            gate.route(platform=platform, action="post", params={}, caller="cdp")
            _check(f"cdp→{platform} blocked", False)
        except DispatchViolationError:
            _check(f"cdp→{platform} blocked", True)


def test_composio_blocked_from_cdp_platforms() -> None:
    print("\n[12] Composio executor blocked from CDP platforms")
    gate = _gate_with_stub()
    for platform in ["tiktok", "instagram"]:
        try:
            gate.route(platform=platform, action="post", params={}, caller="composio")
            _check(f"composio→{platform} blocked", False)
        except DispatchViolationError:
            _check(f"composio→{platform} blocked", True)


# ── Hardening v2 tests ────────────────────────────────────────────────────────

def test_registry_is_frozen() -> None:
    print("\n[13] HARDENING 1: Registry is frozen (MappingProxyType)")
    from platform_dispatch.platform_registry import PLATFORM_REGISTRY
    from types import MappingProxyType
    _check("PLATFORM_REGISTRY is MappingProxyType", isinstance(PLATFORM_REGISTRY, MappingProxyType))
    try:
        PLATFORM_REGISTRY["newplatform"] = Executor.CDP  # type: ignore
        _check("Mutation raises TypeError", False, "no exception")
    except TypeError:
        _check("Mutation raises TypeError", True)


def test_gate_context_active_during_execution() -> None:
    print("\n[14] HARDENING 2: Gate context active during executor call")
    from platform_dispatch import gate_context as ctx

    context_was_active = []

    def _checking_executor(platform, action, params):
        context_was_active.append(ctx.is_active())
        return {"ok": True}

    gate = DispatchGate()
    gate.register_executor(Executor.COMPOSIO, _checking_executor)
    gate.register_executor(Executor.CDP,      _checking_executor)
    gate.register_executor(Executor.FLOW,     _checking_executor)

    gate.route(platform="twitter", action="post", params={})
    _check("gate_context active during executor call", context_was_active == [True])


def test_gate_context_cleared_after_execution() -> None:
    print("\n[15] HARDENING 2: Gate context cleared after executor returns")
    from platform_dispatch import gate_context as ctx

    gate = _gate_with_stub()
    gate.route(platform="twitter", action="post", params={})
    _check("gate_context cleared after route()", not ctx.is_active())


def test_gate_context_cleared_on_exception() -> None:
    print("\n[16] HARDENING 2: Gate context cleared even if executor raises")
    from platform_dispatch import gate_context as ctx

    def _crashing_executor(platform, action, params):
        raise RuntimeError("executor crashed")

    gate = DispatchGate()
    gate.register_executor(Executor.COMPOSIO, _crashing_executor)
    gate.register_executor(Executor.CDP,      _crashing_executor)
    gate.register_executor(Executor.FLOW,     _crashing_executor)

    result = gate.route(platform="twitter", action="post", params={})
    _check("Execution failed gracefully", not result.success)
    _check("gate_context cleared after crash", not ctx.is_active())


def test_require_gate_context_blocks_direct_call() -> None:
    print("\n[17] HARDENING 2: require_gate_context() blocks direct executor call")
    from platform_dispatch.gate_context import require_gate_context
    from platform_dispatch.dispatch_gate import DispatchViolationError

    def _guarded_executor(platform, action, params):
        require_gate_context()  # ← this is what every real executor must do
        return {"ok": True}

    # Call directly (no gate) → must fail
    try:
        _guarded_executor("twitter", "post", {})
        _check("Direct call blocked by require_gate_context", False, "no exception")
    except DispatchViolationError:
        _check("Direct call blocked by require_gate_context", True)


def test_stack_detected_caller_logged() -> None:
    print("\n[18] HARDENING 1: Stack-detected caller in DispatchResult")
    gate = _gate_with_stub()
    result = gate.route(platform="twitter", action="post", params={})
    _check("detected_caller is populated", bool(result.detected_caller),
           f"got: '{result.detected_caller}'")


def test_hostile_caller_blocked() -> None:
    print("\n[19] HARDENING 1: Hostile caller in HOSTILE_CALLERS → blocked")
    from platform_dispatch.dispatch_gate import _HOSTILE_CALLERS
    gate = _gate_with_stub()
    for stem in _HOSTILE_CALLERS:
        try:
            gate.route(platform="twitter", action="post", params={}, caller=stem)
            _check(f"hostile '{stem}' blocked", False, "no exception")
        except DispatchViolationError:
            _check(f"hostile '{stem}' blocked", True)


if __name__ == "__main__":
    print("dispatch gate guard rail tests (hardening v2)")
    print("=" * 50)
    test_platform_routing()
    test_unknown_platform_raises()
    test_forbidden_routes()
    test_allowed_routes()
    test_gate_blocks_mcp_posting()
    test_gate_blocks_internal_dispatch()
    test_gate_allows_correct_routes()
    test_gate_dry_run()
    test_gate_unregistered_executor_raises()
    test_capability_enforcement()
    test_cdp_blocked_from_oauth_platforms()
    test_composio_blocked_from_cdp_platforms()
    # Hardening v2
    test_registry_is_frozen()
    test_gate_context_active_during_execution()
    test_gate_context_cleared_after_execution()
    test_gate_context_cleared_on_exception()
    test_require_gate_context_blocks_direct_call()
    test_stack_detected_caller_logged()
    test_hostile_caller_blocked()
    print(f"\n{'='*50}")
    print(f"RESULT: {_PASS} PASS  {_FAIL} FAIL")
    sys.exit(0 if _FAIL == 0 else 1)

"""
test_harness.py — JARVIS End-to-End Scenario Test

Verifica el pipeline completo sin ejecutar tools reales.
Usa mock executors para aislar cada capa individualmente.

Escenarios críticos:
  1. GREEN path — research Amazon → proceed, deerflow primary
  2. YELLOW path — genera video → proceed + notify
  3. RED path — publica TikTok → bloquea, pide confirmación
  4. RED path — borra archivo → bloquea SIEMPRE (OR-004)
  5. RED path — envía email → bloquea cuando Hernán online
  6. Offline context — genera video cuando Hernán offline → sube a RED
  7. Fallback — primary tool falla → fallback automático a secundaria
  8. Chrome off — flow_director excluido automáticamente
  9. Confirm → execute — ciclo completo con confirmación A/B
 10. Context: primer run → +1 score

Cada test valida:
  - pipeline/action correctos del classifier
  - nivel de riesgo esperado
  - gate decision (proceed/notify/confirm/block)
  - primary tool correcto
  - fallback chain correcta

Uso:
  python3 test_harness.py
  python3 test_harness.py --verbose
"""

from __future__ import annotations

import dataclasses
import sys
import time
from pathlib import Path
from typing import Any

OPERATOR_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(OPERATOR_ROOT))

import hermes_core
from risk_engine import score_intent, pre_execution_gate, RiskContext, GateDecision
from arbitration import arbitrate, ArbitrationResult

# Colores ANSI para output legible
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


# ─── MOCK EXECUTOR ──────────────────────────────────────────────────────────

class MockExecutor:
    """
    Executor falso para tests. Controla qué tools fallan y cuáles tienen éxito.
    Registra qué fue llamado para verificar fallback.
    """
    def __init__(self, failing_tools: list[str] = None):
        self.failing_tools  = set(failing_tools or [])
        self.calls_log: list[tuple[str, dict]] = []  # (tool, params)

    def get_fn(self, tool: str):
        """Retorna callable mock para una tool."""
        def _fn(params: dict, task_id: str) -> dict:
            self.calls_log.append((tool, params))
            if tool in self.failing_tools:
                return {"status": "failed", "error": f"MOCK: {tool} simulated failure"}
            return {"status": "success", "tool_used": tool, "mock": True}
        return _fn

    def build_map(self, tools: list[str]) -> dict:
        return {t: self.get_fn(t) for t in tools}

    def reset(self):
        self.calls_log.clear()


# ─── TEST CASE INFRASTRUCTURE ───────────────────────────────────────────────

class TestResult:
    def __init__(self, name: str):
        self.name   = name
        self.passed = True
        self.checks: list[tuple[bool, str]] = []

    def check(self, condition: bool, description: str, got: Any = None, expected: Any = None):
        if not condition:
            detail = f" (got={got!r}, expected={expected!r})" if got is not None else ""
            self.checks.append((False, f"FAIL: {description}{detail}"))
            self.passed = False
        else:
            self.checks.append((True, f"  ok: {description}"))

    def print(self, verbose: bool = False):
        icon = f"{GREEN}✅{RESET}" if self.passed else f"{RED}❌{RESET}"
        print(f"{icon} {BOLD}{self.name}{RESET}")
        if verbose or not self.passed:
            for ok, msg in self.checks:
                color = GREEN if ok else RED
                print(f"   {color}{msg}{RESET}")


# ─── HELPER ─────────────────────────────────────────────────────────────────

def pipeline_run(text: str, ctx: RiskContext) -> tuple[dict, Any, ArbitrationResult]:
    """
    Corre classify → risk → arbitrate sin ejecutar nada.
    Retorna (intent, risk_result, arb_result).
    """
    intent     = hermes_core.classify(text)
    risk       = score_intent(intent, ctx)
    ctx_dict   = dataclasses.asdict(ctx)
    arb        = arbitrate(intent["pipeline"], intent["action"], risk.allowed_tools, ctx_dict)
    return intent, risk, arb


# ─── SCENARIOS ──────────────────────────────────────────────────────────────

def test_green_research_path(verbose: bool) -> TestResult:
    """
    ESCENARIO 1: Research Amazon → GREEN, deerflow primary, proceed directo.
    Hernán online, no hay historial problemático.
    """
    t = TestResult("Escenario 1: Research Amazon → GREEN path")
    ctx = RiskContext(hernán_online=True, deerflow_available=True, skill_total_runs=5, skill_success_rate=0.9)
    intent, risk, arb = pipeline_run("investiga auriculares amazon", ctx)
    can_proceed, _ = pre_execution_gate(risk)

    t.check(intent["pipeline"] == "research",          "pipeline=research",     intent["pipeline"],    "research")
    t.check(intent["action"]   == "product_research",  "action=product_research")
    t.check(risk.final_level   == "green",             "level=green",           risk.final_level,      "green")
    t.check(risk.gate          == GateDecision.PROCEED, "gate=PROCEED")
    t.check(can_proceed,                               "pre_execution_gate: can_proceed=True")
    t.check(arb.primary_tool   == "deerflow",          "primary_tool=deerflow", arb.primary_tool,      "deerflow")
    t.check("scrapegraph"  in arb.fallback_chain,      "fallback includes scrapegraph")
    t.check("llm_lightweight" in arb.fallback_chain,   "fallback includes llm_lightweight")
    t.print(verbose)
    return t


def test_yellow_video_generation(verbose: bool) -> TestResult:
    """
    ESCENARIO 2: Genera video → YELLOW, ejecuta + notifica.
    Flow Director primary.
    """
    t = TestResult("Escenario 2: Genera video → YELLOW + notify")
    ctx = RiskContext(hernán_online=True, chrome_available=True, comfyui_available=True)
    intent, risk, arb = pipeline_run("genera video smartwatch GPS", ctx)
    can_proceed, _ = pre_execution_gate(risk)

    t.check(risk.final_level   == "yellow",            "level=yellow",          risk.final_level,      "yellow")
    t.check(risk.gate          == GateDecision.NOTIFY, "gate=NOTIFY")
    t.check(can_proceed,                               "pre_execution_gate: can_proceed=True (NOTIFY executes)")
    t.check(arb.primary_tool   == "flow_director",     "primary=flow_director",  arb.primary_tool,     "flow_director")
    t.check(bool(risk.notify_message),                 "notify_message is set")
    t.print(verbose)
    return t


def test_red_tiktok_publish(verbose: bool) -> TestResult:
    """
    ESCENARIO 3: Publica TikTok → RED, BLOQUEA, pide confirmación.
    Hernán online pero acción tiene impacto externo.
    """
    t = TestResult("Escenario 3: Publica TikTok → RED + confirm")
    ctx = RiskContext(hernán_online=True, chrome_available=True)
    intent, risk, arb = pipeline_run("publica el video en tiktok", ctx)
    can_proceed, gate_msg = pre_execution_gate(risk)

    t.check(intent["pipeline"]  == "social_poster",    "pipeline=social_poster", intent["pipeline"], "social_poster")
    t.check(risk.final_level    == "red",              "level=red",              risk.final_level,   "red")
    t.check(risk.gate           == GateDecision.CONFIRM,"gate=CONFIRM")
    t.check(risk.needs_confirm,                        "needs_confirm=True")
    t.check(not can_proceed,                           "pre_execution_gate: BLOCKED (needs confirm)")
    t.check(bool(gate_msg),                            "gate_msg is set (sent to Hernán)")
    t.check("A)" in gate_msg or "Sí" in gate_msg,      "confirm message has A/B options")
    t.print(verbose)
    return t


def test_red_delete_always_blocked(verbose: bool) -> TestResult:
    """
    ESCENARIO 4: Borra archivo → RED SIEMPRE por OR-003+OR-004.
    No importa el contexto: permanent + delete flags.
    """
    t = TestResult("Escenario 4: Borra archivo → RED SIEMPRE (OR-003+OR-004)")
    ctx_online  = RiskContext(hernán_online=True,  skill_total_runs=100)
    ctx_offline = RiskContext(hernán_online=False, hernán_offline_minutes=0)

    for ctx_name, ctx in [("online", ctx_online), ("offline", ctx_offline)]:
        intent, risk, _ = pipeline_run("borra archivo /tmp/test.json", ctx)
        can_proceed, _ = pre_execution_gate(risk)
        t.check(risk.final_level == "red",         f"[{ctx_name}] level=red",         risk.final_level, "red")
        t.check(not can_proceed,                   f"[{ctx_name}] blocked=True")
        t.check("OR-003" in risk.overrides_triggered or "OR-004" in risk.overrides_triggered,
                                                   f"[{ctx_name}] OR-003 or OR-004 triggered")

    t.print(verbose)
    return t


def test_red_email_online(verbose: bool) -> TestResult:
    """
    ESCENARIO 5: Envía email → RED, Hernán online → pide confirmación igualmente.
    External impact + high irreversibility = score ≥ 6.
    """
    t = TestResult("Escenario 5: Envía email → RED (external + irreversible)")
    ctx = RiskContext(hernán_online=True)
    intent, risk, arb = pipeline_run("envía email a cliente@test.com asunto Oferta", ctx)
    can_proceed, _ = pre_execution_gate(risk)

    t.check(intent["pipeline"]  == "email",         "pipeline=email",       intent["pipeline"], "email")
    t.check(risk.final_score    >= 6,               f"score≥6 (got {risk.final_score})")
    t.check(risk.final_level    == "red",           "level=red")
    t.check(not can_proceed,                        "blocked: requiere confirmación")
    t.check(arb.primary_tool    == "gmail_mcp",     "primary=gmail_mcp",    arb.primary_tool, "gmail_mcp")
    t.print(verbose)
    return t


def test_offline_context_elevates_risk(verbose: bool) -> TestResult:
    """
    ESCENARIO 6: Genera video cuando Hernán offline 3h → sube a RED.
    Yellow base + offline modifier (+1) + automated_loop (+1) → puede subir.
    """
    t = TestResult("Escenario 6: Video offline >2h → score sube vs online")
    ctx_online  = RiskContext(hernán_online=True,  hernán_offline_minutes=0,   in_automated_loop=False)
    ctx_offline = RiskContext(hernán_online=False, hernán_offline_minutes=180, in_automated_loop=True)

    _, risk_on,  _ = pipeline_run("genera video smartwatch", ctx_online)
    _, risk_off, _ = pipeline_run("genera video smartwatch", ctx_offline)

    t.check(risk_on.final_score  < risk_off.final_score,
            f"offline score ({risk_off.final_score}) > online ({risk_on.final_score})")
    t.check(risk_on.final_level  == "yellow",    "online=yellow",  risk_on.final_level,  "yellow")
    # offline + automated loop: at minimum yellow, likely red
    t.check(risk_off.final_score >= risk_on.final_score,  "offline ≥ online score")
    t.print(verbose)
    return t


def test_fallback_on_primary_failure(verbose: bool) -> TestResult:
    """
    ESCENARIO 7: Tool primaria falla → fallback automático a secundaria.
    Simula DeerFlow caído → scrapegraph toma el relevo.
    """
    t = TestResult("Escenario 7: Fallback automático — deerflow falla → scrapegraph")
    ctx = RiskContext(hernán_online=True, deerflow_available=True)
    ctx_dict = dataclasses.asdict(ctx)
    intent   = hermes_core.classify("investiga auriculares amazon")
    risk     = score_intent(intent, ctx)
    arb      = arbitrate("research", "product_research", risk.allowed_tools, ctx_dict)

    # Mock: deerflow falla, scrapegraph tiene éxito
    mock     = MockExecutor(failing_tools=["deerflow"])
    exec_map = mock.build_map(arb.fallback_chain)

    from arbitration import execute_with_fallback
    result = execute_with_fallback(arb, exec_map, intent["params"], task_id="TEST-FALLBACK")

    t.check(result["status"]       == "success",      "result=success (fallback worked)")
    t.check(result["tool_used"]    != "deerflow",     "did NOT use deerflow (it failed)")
    t.check(result["tool_fallback"] == True,           "tool_fallback=True")
    t.check(len(mock.calls_log)    >= 2,               f"at least 2 tools tried (got {len(mock.calls_log)})")
    t.check(mock.calls_log[0][0]   == "deerflow",      "first attempt=deerflow")

    t.print(verbose)
    return t


def test_chrome_off_excludes_flow_director(verbose: bool) -> TestResult:
    """
    ESCENARIO 8: Chrome no disponible → flow_director excluido automáticamente.
    ComfyUI toma el relevo como primary.
    """
    t = TestResult("Escenario 8: Chrome OFF → flow_director excluido, comfyui primary")
    ctx = RiskContext(hernán_online=True, chrome_available=False, comfyui_available=True)
    intent, risk, arb = pipeline_run("genera video smartwatch GPS", ctx)

    t.check("flow_director" not in arb.fallback_chain,
            "flow_director NOT in chain (Chrome unavailable)")
    t.check(arb.primary_tool == "comfyui",             "primary=comfyui",   arb.primary_tool, "comfyui")
    t.print(verbose)
    return t


def test_confirm_cycle(verbose: bool) -> TestResult:
    """
    ESCENARIO 9: Ciclo completo confirm → A → execute.
    Simula almacenar confirmación en SQLite y recuperarla.
    """
    t = TestResult("Escenario 9: Confirm cycle → A → execute (SQLite store/retrieve)")
    import task_manager
    task_manager.init_db()

    ctx = RiskContext(hernán_online=True, chrome_available=True)
    intent, risk, arb = pipeline_run("publica el video en tiktok", ctx)
    _, gate_msg = pre_execution_gate(risk)

    # Simula gateway almacenando confirmación pendiente
    chat_id = 9999999
    task_manager.clear_confirmation(chat_id)  # limpiar si existía
    task_manager.store_confirmation(chat_id, intent, dataclasses.asdict(risk))

    # Simula Hernán respondiendo "A"
    pending = task_manager.get_confirmation(chat_id)
    t.check(pending is not None,                       "confirmation stored in SQLite")

    if pending:
        retrieved_intent, retrieved_risk = pending
        task_manager.clear_confirmation(chat_id)

        t.check(retrieved_intent["pipeline"] == "social_poster",   "retrieved pipeline=social_poster")
        t.check(retrieved_intent["action"]   == "post_tiktok",     "retrieved action=post_tiktok")
        t.check(retrieved_risk["final_level"] == "red",            "retrieved level=red")
        t.check(task_manager.get_confirmation(chat_id) is None,    "confirmation cleared after retrieval")

    t.print(verbose)
    return t


def test_first_run_modifier(verbose: bool) -> TestResult:
    """
    ESCENARIO 10: Primer run de skill → +1 score.
    research con 0 runs vs 10 runs deben tener scores distintos.
    """
    t = TestResult("Escenario 10: Primera ejecución → +1 score")
    ctx_first = RiskContext(hernán_online=True, skill_total_runs=0,  skill_success_rate=1.0)
    ctx_exp   = RiskContext(hernán_online=True, skill_total_runs=10, skill_success_rate=1.0)

    intent = {"pipeline": "research", "action": "product_research", "params": {}}
    risk_first = score_intent(intent, ctx_first)
    risk_exp   = score_intent(intent, ctx_exp)

    t.check(risk_first.final_score > risk_exp.final_score,
            f"first_run score ({risk_first.final_score}) > experienced ({risk_exp.final_score})")
    t.check(risk_first.context_delta >= 1,  "first_run context_delta ≥ 1")
    t.check(risk_exp.context_delta   == 0,  "experienced context_delta = 0")
    t.print(verbose)
    return t


def test_read_email_online_vs_offline(verbose: bool) -> TestResult:
    """
    BONUS: Leer correo online → GREEN. Leer correo offline → RED (OR-007).
    """
    t = TestResult("Bonus: read_email → GREEN online, RED offline")
    ctx_on  = RiskContext(hernán_online=True,  hernán_offline_minutes=0)
    ctx_off = RiskContext(hernán_online=False, hernán_offline_minutes=60)

    intent_on = {"pipeline": "email", "action": "read_email", "params": {}}
    risk_on   = score_intent(intent_on, ctx_on)
    risk_off  = score_intent(intent_on, ctx_off)

    t.check(risk_on.final_level  in ("green", "yellow"), f"online: level≤yellow (got {risk_on.final_level})")
    t.check(risk_off.final_level == "red",               f"offline: level=red (got {risk_off.final_level})")
    t.check("OR-007" in risk_off.overrides_triggered,    "OR-007 triggered when offline")
    t.print(verbose)
    return t


# ─── RUNNER ──────────────────────────────────────────────────────────────────

def run_all(verbose: bool = False) -> bool:
    import task_manager
    task_manager.init_db()

    print(f"\n{BOLD}{'='*55}")
    print("  JARVIS SYSTEM — End-to-End Test Harness")
    print(f"{'='*55}{RESET}\n")

    started = time.monotonic()

    all_tests = [
        test_green_research_path,
        test_yellow_video_generation,
        test_red_tiktok_publish,
        test_red_delete_always_blocked,
        test_red_email_online,
        test_offline_context_elevates_risk,
        test_fallback_on_primary_failure,
        test_chrome_off_excludes_flow_director,
        test_confirm_cycle,
        test_first_run_modifier,
        test_read_email_online_vs_offline,
    ]

    results = [fn(verbose) for fn in all_tests]
    passed  = sum(1 for r in results if r.passed)
    total   = len(results)
    elapsed = round(time.monotonic() - started, 2)

    print(f"\n{BOLD}{'─'*55}{RESET}")
    if passed == total:
        print(f"{GREEN}{BOLD}✅ TODOS PASAN: {passed}/{total} ({elapsed}s){RESET}")
    else:
        failed = total - passed
        print(f"{RED}{BOLD}❌ FALLOS: {failed}/{total} | Pasan: {passed}/{total} ({elapsed}s){RESET}")

    return passed == total


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    ok = run_all(verbose)
    sys.exit(0 if ok else 1)

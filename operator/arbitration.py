"""
arbitration.py — Multi-Backend Resolution System

NO es un selector simple. Es un sistema de resolución con:
  - Reliability scoring por herramienta (histórico + default)
  - Fallback automático en cascada si tool falla
  - Selección dinámica según contexto (Chrome disponible, GPU, etc.)
  - Sin lógica de policy — eso lo hace risk_engine

POSICIÓN en el pipeline:
  classify → risk_engine → [arbitration] → execution → trace

INVARIANTE:
  arbitrate() siempre devuelve al menos una tool.
  Si no hay ninguna disponible → devuelve ["fallback_llm"] con advertencia.

Versión: 1.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("arbitration")

# ─── DEFAULT RELIABILITY SCORES ──────────────────────────────────────────────
# Basado en experiencia real del sistema (se sobreescriben con datos históricos).
# Escala 0.0-1.0. Herramientas más confiables primero dentro de cada pipeline.

DEFAULT_RELIABILITY: dict[str, float] = {
    # Web / browsing
    "playwright_mcp":       0.92,
    "browser_use":          0.68,   # parcialmente funcional (mem issues)
    "scrapegraph":          0.75,

    # Research
    "deerflow":             0.80,   # requiere auth, puede fallar en cold start
    "llm_lightweight":      0.95,   # siempre disponible, menos profundo

    # Media — video / carousel
    "flow_director":        0.85,   # requiere Chrome CDP
    "carousel_flow":        0.85,   # requiere Chrome CDP
    "comfyui":              0.78,
    "fooocus":              0.72,

    # Social
    "tiktok_playwright":    0.82,   # requiere Chrome + cookies válidas
    "instagram_instagrapi": 0.88,
    "youtube_executor":     0.80,   # requiere Chrome CDP + Google session
    "facebook_executor":    0.78,   # requiere Chrome CDP + FB session
    "pinterest_executor":   0.82,   # requiere Chrome CDP + Pinterest session
    "twitter_executor":     0.80,   # requiere Chrome CDP + X cookies

    # Communication
    "gmail_mcp":            0.95,
    "whatsapp_executor":    0.70,   # requiere OpenWA setup

    # Docs
    "docx_skill":           0.98,
    "pdf_skill":            0.98,
    "xlsx_skill":           0.97,
    "pptx_skill":           0.96,

    # System
    "hermes_status":        0.99,
    "filesystem_mcp":       0.99,

    # Twitter / X
    "x_api":                0.75,

    # Fallback universal
    "fallback_llm":         0.60,
}

# ─── PIPELINE → PREFERRED TOOL ORDER ─────────────────────────────────────────
# Orden preferido cuando no hay datos históricos.
# risk_engine ya filtró las allowed_tools — aquí solo reordenamos.

PIPELINE_PREFERENCE: dict[tuple[str, str], list[str]] = {
    # Full content pipeline (research + video + post)
    ("content_pipeline", "research_and_create"): ["pipeline_full"],

    # Research
    ("research", "product_research"):    ["deerflow", "scrapegraph", "llm_lightweight"],
    ("research", "web_search"):          ["playwright_mcp", "scrapegraph", "llm_lightweight"],

    # Media
    ("mediafactory", "create_video"):    ["flow_director", "comfyui", "fooocus"],
    ("flow_director", "generate_video"):    ["flow_director", "comfyui"],
    ("flow_director", "generate_image"):    ["comfyui", "fooocus"],
    ("flow_director", "generate_carousel"): ["carousel_flow"],
    ("comfy", "generate"):               ["comfyui"],

    # Social
    ("social_poster", "post_tiktok"):    ["tiktok_playwright"],
    ("social_poster", "post_instagram"): ["instagram_instagrapi"],
    ("social_poster", "post_youtube"):   ["youtube_executor"],
    ("social_poster", "post_facebook"):  ["facebook_executor"],
    ("social_poster", "post_pinterest"): ["pinterest_executor"],
    ("social_poster", "post_twitter"):   ["twitter_executor"],
    ("social_poster", "post_x"):         ["twitter_executor"],
    ("social_poster", "post"):           ["tiktok_playwright", "instagram_instagrapi", "youtube_executor", "facebook_executor", "pinterest_executor", "twitter_executor"],

    # Web
    ("browser", "browse"):               ["playwright_mcp", "browser_use", "scrapegraph"],
    ("browser", "extract_data"):         ["scrapegraph", "playwright_mcp"],

    # Email
    ("email", "send_email"):             ["gmail_mcp"],
    ("email", "read_email"):             ["gmail_mcp"],

    # WhatsApp
    ("whatsapp", "send_message"):        ["whatsapp_executor"],

    # Docs
    ("docs", "create_document"):         ["docx_skill"],
    ("docs", "create_spreadsheet"):      ["xlsx_skill"],
    ("docs", "create_presentation"):     ["pptx_skill"],
    ("docs", "create_pdf"):              ["pdf_skill"],

    # System
    ("system", "status"):                ["hermes_status"],
    ("system", "revenue"):               ["hermes_status"],
    ("system", "tasks"):                 ["hermes_status"],
    ("system", "delete_file"):           ["filesystem_mcp"],
    ("system", "answer_question"):       ["llm_lightweight"],
    ("system", "pause_pipeline"):        ["hermes_status"],
}

# ─── AVAILABILITY CHECKS ──────────────────────────────────────────────────────
# Funciones rápidas (sin llamadas de red) que verifican disponibilidad.
# Usamos el contexto que risk_engine ya construyó.

def _tool_available(tool: str, context_dict: dict) -> bool:
    """
    Verifica si una herramienta está disponible en el contexto actual.
    context_dict: serialización de RiskContext o equivalente.
    """
    chrome_ok  = context_dict.get("chrome_available", True)
    comfy_ok   = context_dict.get("comfyui_available", True)
    deer_ok    = context_dict.get("deerflow_available", True)

    availability_map = {
        "playwright_mcp":       chrome_ok,
        "tiktok_playwright":    chrome_ok,
        "flow_director":        chrome_ok,
        "carousel_flow":        chrome_ok,
        "browser_use":          chrome_ok,
        "comfyui":              comfy_ok,
        "fooocus":              comfy_ok,
        "deerflow":             deer_ok,
        # Siempre disponibles (no requieren servicios externos locales)
        "scrapegraph":          True,
        "llm_lightweight":      True,
        "gmail_mcp":            True,
        "whatsapp_executor":    True,
        "instagram_instagrapi": True,
        "youtube_executor":     chrome_ok,
        "facebook_executor":    chrome_ok,
        "pinterest_executor":   chrome_ok,
        "twitter_executor":     chrome_ok,
        "hermes_status":        True,
        "filesystem_mcp":       True,
        "docx_skill":           True,
        "pdf_skill":            True,
        "xlsx_skill":           True,
        "pptx_skill":           True,
        "x_api":                True,
        "fallback_llm":         True,
    }
    return availability_map.get(tool, True)


# ─── RELIABILITY SCORER ──────────────────────────────────────────────────────

def _get_reliability(tool: str, db_path: Optional[str] = None) -> float:
    """
    Retorna reliability score para una tool.
    Orden: DB histórica (si hay ≥5 registros) → default hardcoded
    """
    if db_path:
        try:
            # Import aquí para evitar circular imports
            import sys
            import os
            operator_root = os.path.dirname(os.path.abspath(__file__))
            if operator_root not in sys.path:
                sys.path.insert(0, operator_root)
            import task_manager
            historical = task_manager.get_tool_reliability(tool, min_samples=5)
            if historical is not None:
                return historical
        except Exception as e:
            log.debug(f"No historical data for {tool}: {e}")

    return DEFAULT_RELIABILITY.get(tool, 0.50)


# ─── MAIN ARBITRATION FUNCTION ───────────────────────────────────────────────

@dataclass
class ArbitrationResult:
    primary_tool: str                   # herramienta a intentar primero
    fallback_chain: list[str]           # lista ordenada: primary + fallbacks
    all_unavailable: bool = False       # True si no hay nada disponible
    reason: str = ""                    # para debug/logging


def arbitrate(
    pipeline: str,
    action: str,
    allowed_tools: list[str],          # ya filtrado por risk_engine
    context_dict: dict,                # dict de RiskContext o equivalente
    db_path: Optional[str] = None,
) -> ArbitrationResult:
    """
    Selecciona la mejor herramienta para ejecutar la acción.
    Devuelve chain ordenada: [mejor, fallback1, fallback2, ...]

    El executor usa este orden: intenta primary, si falla → fallback_chain[1], etc.

    Args:
        pipeline:       pipeline del intent (ej: "research")
        action:         acción del intent (ej: "product_research")
        allowed_tools:  herramientas permitidas por risk_engine (ya filtradas)
        context_dict:   estado del sistema para verificar disponibilidad
        db_path:        ruta a tasks.db para reliability histórica (opcional)
    """
    if not allowed_tools:
        log.warning(f"arbitrate({pipeline}.{action}): no allowed_tools → fallback_llm")
        return ArbitrationResult(
            primary_tool="fallback_llm",
            fallback_chain=["fallback_llm"],
            all_unavailable=False,
            reason="No tools allowed by risk_engine, using fallback_llm",
        )

    # 1. Obtener orden preferido para este pipeline+action
    preferred_order = PIPELINE_PREFERENCE.get((pipeline, action), [])

    # 2. Filtrar allowed_tools por disponibilidad real
    available = [t for t in allowed_tools if _tool_available(t, context_dict)]

    if not available:
        log.warning(f"arbitrate({pipeline}.{action}): all tools unavailable, using fallback_llm")
        return ArbitrationResult(
            primary_tool="fallback_llm",
            fallback_chain=["fallback_llm"],
            all_unavailable=True,
            reason=f"All tools unavailable: {allowed_tools}",
        )

    # 3. Sort strategy:
    #    a) Preference order DOMINATES (lower index = higher priority)
    #    b) Reliability is secondary: used to skip tools below min threshold
    #       and to break ties between tools at the same preference tier
    #    c) Tools with no preference entry go last, sorted by reliability

    MIN_RELIABILITY = 0.40  # tools below this are moved to end of chain

    def sort_key(tool: str) -> tuple:
        pref_pos    = preferred_order.index(tool) if tool in preferred_order else 999
        reliability = _get_reliability(tool, db_path)
        # Below-threshold tools get pushed to the end
        tier        = 0 if reliability >= MIN_RELIABILITY else 1
        # Within same tier and preference position, higher reliability wins
        return (tier, pref_pos, -reliability)

    ordered_tools = sorted(available, key=sort_key)

    primary   = ordered_tools[0]
    fallbacks = ordered_tools[1:] if len(ordered_tools) > 1 else []

    log.info(
        f"arbitrate({pipeline}.{action}): primary={primary} "
        f"fallbacks={fallbacks} "
        f"(reliability={_get_reliability(primary, db_path):.2f})"
    )

    return ArbitrationResult(
        primary_tool=primary,
        fallback_chain=ordered_tools,
        reason=f"primary={primary} reliability={_get_reliability(primary, db_path):.2f}",
    )


# ─── EXECUTOR WRAPPER — FALLBACK EN CASCADA ─────────────────────────────────

def execute_with_fallback(
    arb_result: ArbitrationResult,
    executor_fn: "dict[str, callable]",
    params: dict,
    task_id: str = "",
    db_path: Optional[str] = None,
    pipeline: str = "",
    action: str = "",
) -> dict:
    """
    Ejecuta la acción intentando cada tool en orden.
    Si una falla → siguiente en fallback_chain.
    Registra trace de cada intento.

    Args:
        arb_result:   resultado de arbitrate()
        executor_fn:  dict {tool_name: callable(params, task_id) → dict}
                      callable retorna {"status": "success"|"failed", ...}
        params:       params del intent
        task_id:      para logging
        db_path:      para registrar traces

    Returns:
        resultado del primer executor exitoso, o {"status": "failed", ...}
    """
    import time

    last_error = ""

    for i, tool in enumerate(arb_result.fallback_chain):
        fn = executor_fn.get(tool)
        if not fn:
            log.warning(f"[{task_id}] No executor for tool={tool}, skipping")
            continue

        is_fallback = i > 0
        started_at  = time.monotonic()

        try:
            log.info(f"[{task_id}] Trying tool={tool} (fallback={is_fallback})")
            result = fn(params, task_id)
            ended_at = time.monotonic()

            if result.get("status") == "success":
                # Registrar trace exitoso
                if db_path:
                    _log_trace_safe(
                        task_id=task_id,
                        tool=tool,
                        success=True,
                        started_at=started_at,
                        ended_at=ended_at,
                        is_fallback=is_fallback,
                        db_path=db_path,
                        pipeline=pipeline,
                        action=action,
                    )
                result["tool_used"]     = tool
                result["tool_fallback"] = is_fallback
                return result

            # Tool returned failure explicitly
            last_error = result.get("error", "unknown error")
            log.warning(f"[{task_id}] Tool {tool} returned failure: {last_error}")

            if db_path:
                _log_trace_safe(
                    task_id=task_id,
                    tool=tool,
                    success=False,
                    started_at=started_at,
                    ended_at=time.monotonic(),
                    is_fallback=is_fallback,
                    error=last_error,
                    db_path=db_path,
                    pipeline=pipeline,
                    action=action,
                )

        except Exception as e:
            last_error = str(e)
            ended_at = time.monotonic()
            log.warning(f"[{task_id}] Tool {tool} crashed: {e}")

            if db_path:
                _log_trace_safe(
                    task_id=task_id,
                    tool=tool,
                    success=False,
                    started_at=started_at,
                    ended_at=ended_at,
                    is_fallback=is_fallback,
                    error=last_error,
                    db_path=db_path,
                )

    # All tools exhausted
    log.error(f"[{task_id}] All tools failed. Last error: {last_error}")
    return {
        "status":  "failed",
        "error":   f"All tools exhausted. Last: {last_error}",
        "tools_tried": arb_result.fallback_chain,
    }


def _log_trace_safe(
    task_id: str,
    tool: str,
    success: bool,
    started_at: float,
    ended_at: float,
    is_fallback: bool,
    error: str = "",
    db_path: str = "",
    pipeline: str = "",
    action: str = "",
):
    """Registra trace sin crashear aunque falle."""
    try:
        import sys
        import os
        operator_root = os.path.dirname(os.path.abspath(__file__))
        if operator_root not in sys.path:
            sys.path.insert(0, operator_root)
        import task_manager
        task_manager.log_trace(
            task_id=task_id,
            pipeline=pipeline,
            action=action,
            tool_used=tool,
            success=success,
            started_at=started_at,
            ended_at=ended_at,
            tool_fallback=is_fallback,
            error=error,
        )
    except Exception as e:
        log.debug(f"trace logging failed (non-critical): {e}")


# ─── QUICK TEST ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from risk_engine import RiskContext
    import dataclasses

    ctx = RiskContext(
        hernán_online=True,
        chrome_available=True,
        comfyui_available=True,
        deerflow_available=True,
    )
    ctx_dict = dataclasses.asdict(ctx)

    tests = [
        # (pipeline, action, allowed_tools, expected_primary)
        ("research",      "product_research",  ["deerflow", "scrapegraph", "llm_lightweight"], "deerflow"),
        ("mediafactory",  "create_video",      ["flow_director", "comfyui", "fooocus"],        "flow_director"),
        ("browser",       "browse",            ["playwright_mcp", "browser_use", "scrapegraph"], "playwright_mcp"),
        ("social_poster", "post_tiktok",       ["tiktok_playwright"],                          "tiktok_playwright"),
        # Chrome NO disponible — flow_director debe quedar fuera
        ("mediafactory",  "create_video",      ["flow_director", "comfyui"],                   "comfyui"),
    ]

    ctx_no_chrome_dict = dataclasses.asdict(
        RiskContext(hernán_online=True, chrome_available=False, comfyui_available=True)
    )

    print("=== ARBITRATION TESTS ===")
    for i, (pipeline, action, tools, expected) in enumerate(tests):
        ctx_use = ctx_no_chrome_dict if i == 4 else ctx_dict
        result = arbitrate(pipeline, action, tools, ctx_use)
        ok = result.primary_tool == expected
        icon = "✅" if ok else "❌"
        print(f"{icon} [{pipeline}.{action}]")
        print(f"   primary={result.primary_tool} | chain={result.fallback_chain}")
        if not ok:
            print(f"   ❌ expected {expected}, got {result.primary_tool}")

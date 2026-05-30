"""
execution_orchestrator.py — Unified Execution Contract

PROPÓSITO:
  Capa puente entre arbitration.ArbitrationResult y los executors reales.
  Garantiza contrato único sin importar qué tool ejecute:
    - mismo logging
    - mismo retry policy
    - mismo error handling
    - mismo trace format
    - adaptación de params por tool (normalización de firma)

POSICIÓN en el pipeline:
  classify → risk_engine → arbitration → [execution_orchestrator] → executors

INVARIANTE:
  execute() SIEMPRE retorna un dict con al menos:
    {"status": "success"|"failed", "tool_used": str, "tool_fallback": bool}

NO CONTIENE:
  - lógica de negocio
  - lógica de policy
  - selección de tools (eso es arbitration)
  - clasificación de intents (eso es hermes_core)

Versión: 1.0
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Callable

# ─── Setup paths ──────────────────────────────────────────────────────────────
OPERATOR_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(OPERATOR_ROOT))

from arbitration import ArbitrationResult, execute_with_fallback

log = logging.getLogger("execution_orchestrator")

DB_PATH = str(OPERATOR_ROOT / "tasks.db")


# ─── PARAM ADAPTERS ──────────────────────────────────────────────────────────
# Cada executor tiene firma distinta. El adaptador normaliza params: dict
# al formato que cada tool espera. Mantiene los executors sin modificar.

def _adapt_for_tool(tool: str, pipeline: str, action: str, params: dict) -> dict:
    """
    Retorna params adaptados para una tool específica.
    El resultado se pasa como **kwargs al wrapper de cada tool.
    """
    adapted = dict(params)  # never mutate the original

    # browser_executor.browse(task: str, task_id: str)
    # Extrae "question" del dict
    if tool in ("playwright_mcp", "browser_use"):
        adapted["_task_str"] = (
            params.get("question") or
            params.get("task") or
            params.get("url") or
            str(params)
        )

    # research_executor.research_product(query: str, task_id: str)
    elif tool in ("deerflow", "scrapegraph", "llm_lightweight") and pipeline == "research":
        adapted["_query_str"] = (
            params.get("topic") or
            params.get("intent") or
            params.get("query") or
            str(params)
        )

    # whatsapp_executor.send_message(phone: str, text: str, session: str)
    elif tool == "whatsapp_executor":
        adapted["_phone"] = params.get("phone", "")
        adapted["_text"]  = params.get("message", params.get("text", ""))

    # Social posting — pass-through, executors accept full params dict
    elif tool in ("tiktok_playwright", "instagram_instagrapi",
                  "youtube_executor", "facebook_executor",
                  "pinterest_executor", "twitter_executor"):
        # Normalize common aliases
        adapted["video_path"]  = params.get("video_path", params.get("media_path", ""))
        adapted["caption"]     = params.get("caption", params.get("text", params.get("description", "")))
        adapted["title"]       = params.get("title", params.get("caption", "")[:100])
        adapted["description"] = params.get("description", params.get("caption", ""))
        adapted["link"]        = params.get("link", params.get("affiliate_url", ""))
        adapted["tags"]        = params.get("tags", [])

    return adapted


# ─── EXECUTOR REGISTRY ───────────────────────────────────────────────────────
# Mapea tool_name → callable(params: dict, task_id: str) → dict
# Todos los wrappers tienen firma idéntica para execute_with_fallback.

def _build_executor_map(pipeline: str, action: str) -> dict[str, Callable]:
    """
    Construye el mapa tool → callable para este pipeline+action.
    Importaciones lazy para no fallar si un executor tiene dependencias no instaladas.
    """
    executors: dict[str, Callable] = {}

    # ── Research ──────────────────────────────────────────────────────────────
    try:
        from executors import research_executor

        def _deerflow_wrapper(params: dict, task_id: str) -> dict:
            query = params.get("_query_str", params.get("topic", str(params)))
            return research_executor.research_product(query, task_id)

        def _scrapegraph_wrapper(params: dict, task_id: str) -> dict:
            query = params.get("_query_str", params.get("topic", str(params)))
            # ScrapeGraph Amazon research — usa amazon_research_runtime.py
            try:
                scrapegraph_path = Path("/Volumes/OPENCLAW_STORAG 1/AI_TOOLS/scrapegraph")
                sys.path.insert(0, str(scrapegraph_path))
                from amazon_research_runtime import AmazonResearchRuntime
                runtime = AmazonResearchRuntime()
                products = runtime.search_amazon_products(query, max_results=3)
                return {
                    "status":  "success",
                    "brief":   products[0] if products else {},
                    "source":  "scrapegraph",
                    "summary": f"🔍 ScrapeGraph: {len(products)} productos encontrados para '{query}'",
                }
            except Exception as e:
                return {"status": "failed", "error": f"scrapegraph: {e}"}

        def _llm_lightweight_wrapper(params: dict, task_id: str) -> dict:
            query = params.get("_query_str", params.get("topic", str(params)))
            return research_executor._research_lightweight.__wrapped__(query) \
                if hasattr(research_executor._research_lightweight, "__wrapped__") \
                else research_executor.research_product(query, task_id)

        executors["deerflow"]        = _deerflow_wrapper
        executors["scrapegraph"]     = _scrapegraph_wrapper
        executors["llm_lightweight"] = _llm_lightweight_wrapper

    except ImportError as e:
        log.warning(f"research_executor not available: {e}")

    # ── Content Pipeline (research → video → post) ───────────────────────────
    try:
        from executors import content_pipeline_executor

        executors["pipeline_full"] = content_pipeline_executor.research_and_create

    except ImportError as e:
        log.warning(f"content_pipeline_executor not available: {e}")

    # ── Media — Video ─────────────────────────────────────────────────────────
    try:
        from executors import flow_executor, mediafactory_executor

        if action == "create_video":
            executors["flow_director"] = mediafactory_executor.generate_and_post
        else:
            executors["flow_director"] = lambda p, t: flow_executor.generate_video(p, t)

        executors["carousel_flow"] = lambda p, t: flow_executor.generate_carousel(p, t)

        executors["comfyui"] = lambda p, t: {
            "status": "failed",
            "error": "ComfyUI executor pendiente de implementar"
        }
        executors["fooocus"] = lambda p, t: {
            "status": "failed",
            "error": "Fooocus executor: ver fooocus_executor.py"
        }

    except ImportError as e:
        log.warning(f"media executors not available: {e}")

    # ── Media — Imagen ────────────────────────────────────────────────────────
    try:
        from executors import flow_executor as _fe
        executors["comfyui_image"] = lambda p, t: _fe.generate_image(p, t)
    except ImportError:
        pass

    # ── Web / Browser ─────────────────────────────────────────────────────────
    try:
        from executors import browser_executor

        def _playwright_wrapper(params: dict, task_id: str) -> dict:
            task = params.get("_task_str", params.get("question", str(params)))
            return browser_executor.browse(task, task_id)

        def _browser_use_wrapper(params: dict, task_id: str) -> dict:
            task = params.get("_task_str", params.get("question", str(params)))
            return browser_executor.browse(task, task_id)  # same executor, same Chrome

        executors["playwright_mcp"] = _playwright_wrapper
        executors["browser_use"]    = _browser_use_wrapper

    except ImportError as e:
        log.warning(f"browser_executor not available: {e}")

    # ScrapeGraph as browser fallback
    def _scrapegraph_browse(params: dict, task_id: str) -> dict:
        try:
            scrapegraph_path = Path("/Volumes/OPENCLAW_STORAG 1/AI_TOOLS/scrapegraph")
            sys.path.insert(0, str(scrapegraph_path))
            from amazon_research_runtime import AmazonResearchRuntime
            url = params.get("url") or params.get("_task_str", "")
            runtime = AmazonResearchRuntime()
            result = runtime.extract_affiliate_ready_data({"url": url})
            return {"status": "success", "data": result, "source": "scrapegraph"}
        except Exception as e:
            return {"status": "failed", "error": f"scrapegraph_browse: {e}"}

    executors["scrapegraph"] = executors.get("scrapegraph") or _scrapegraph_browse

    # ── Social ────────────────────────────────────────────────────────────────

    # TikTok
    try:
        from executors import tiktok_executor as _tik
        def _tiktok_wrapper(params: dict, task_id: str) -> dict:
            return _tik.post_video(params, task_id)
        executors["tiktok_playwright"] = _tiktok_wrapper
    except ImportError:
        def _tiktok_stub(params: dict, task_id: str) -> dict:
            return {"status": "failed", "error": "tiktok_executor not installed"}
        executors["tiktok_playwright"] = _tiktok_stub

    # Instagram
    try:
        from executors import instagram_executor as _ig
        def _instagram_wrapper(params: dict, task_id: str) -> dict:
            return _ig.post_reel(params, task_id)
        executors["instagram_instagrapi"] = _instagram_wrapper
    except ImportError:
        def _instagram_stub(params: dict, task_id: str) -> dict:
            return {"status": "failed", "error": "instagram_executor not installed"}
        executors["instagram_instagrapi"] = _instagram_stub

    # YouTube
    try:
        from executors import youtube_executor as _yt
        def _youtube_wrapper(params: dict, task_id: str) -> dict:
            return _yt.post_video(params, task_id)
        executors["youtube_executor"] = _youtube_wrapper
    except ImportError as e:
        _youtube_err = str(e)
        def _youtube_stub(params: dict, task_id: str) -> dict:
            return {"status": "failed", "error": f"youtube_executor import error: {_youtube_err}"}
        executors["youtube_executor"] = _youtube_stub

    # Facebook
    try:
        from executors import facebook_executor as _fb
        def _facebook_wrapper(params: dict, task_id: str) -> dict:
            return _fb.post_reel(params, task_id)
        executors["facebook_executor"] = _facebook_wrapper
    except ImportError as e:
        _facebook_err = str(e)
        def _facebook_stub(params: dict, task_id: str) -> dict:
            return {"status": "failed", "error": f"facebook_executor import error: {_facebook_err}"}
        executors["facebook_executor"] = _facebook_stub

    # Pinterest
    try:
        from executors import pinterest_executor as _pin
        def _pinterest_wrapper(params: dict, task_id: str) -> dict:
            return _pin.create_pin(params, task_id)
        executors["pinterest_executor"] = _pinterest_wrapper
    except ImportError as e:
        _pinterest_err = str(e)
        def _pinterest_stub(params: dict, task_id: str) -> dict:
            return {"status": "failed", "error": f"pinterest_executor import error: {_pinterest_err}"}
        executors["pinterest_executor"] = _pinterest_stub

    # Twitter / X
    try:
        from executors import twitter_executor as _tw
        def _twitter_wrapper(params: dict, task_id: str) -> dict:
            return _tw.post_tweet(params, task_id)
        executors["twitter_executor"] = _twitter_wrapper
    except ImportError as e:
        _twitter_err = str(e)
        def _twitter_stub(params: dict, task_id: str) -> dict:
            return {"status": "failed", "error": f"twitter_executor import error: {_twitter_err}"}
        executors["twitter_executor"] = _twitter_stub

    # ── Email ─────────────────────────────────────────────────────────────────
    def _gmail_wrapper(params: dict, task_id: str) -> dict:
        """Gmail via MCP — retorna instrucción al gateway para usar tool MCP."""
        return {
            "status":       "mcp_delegate",
            "mcp_tool":     "gmail",
            "mcp_action":   action,
            "params":       params,
            "note": "Gmail MCP debe ser llamado desde el gateway async context"
        }

    executors["gmail_mcp"] = _gmail_wrapper

    # ── WhatsApp ──────────────────────────────────────────────────────────────
    try:
        from executors import whatsapp_executor

        def _whatsapp_wrapper(params: dict, task_id: str) -> dict:
            phone = params.get("_phone") or params.get("phone", "")
            text  = params.get("_text")  or params.get("message", params.get("text", ""))
            if not phone or not text:
                return {"status": "failed", "error": "phone y message son requeridos"}
            result = whatsapp_executor.send_message(phone, text)
            return {"status": "success" if result.get("success") else "failed", **result}

        executors["whatsapp_executor"] = _whatsapp_wrapper

    except ImportError as e:
        log.warning(f"whatsapp_executor not available: {e}")

    # ── System ────────────────────────────────────────────────────────────────
    try:
        import hermes_core

        def _status_wrapper(params: dict, task_id: str) -> dict:
            s = hermes_core.get_real_status()
            return {"status": "success", "data": s, "formatted": hermes_core.format_status(s)}

        executors["hermes_status"] = _status_wrapper

    except ImportError:
        executors["hermes_status"] = lambda p, t: {
            "status": "success", "data": {}, "formatted": "Estado no disponible"
        }

    # ── Fallback universal ────────────────────────────────────────────────────
    executors["fallback_llm"] = lambda p, t: {
        "status": "failed",
        "error":  "Ninguna herramienta disponible para esta acción. Intenta con un comando más específico."
    }

    return executors


# ─── META-COGNITIVE HANDLER ──────────────────────────────────────────────────

def _execute_meta_cognitive(intent: dict, task_id: str) -> dict:
    """
    Handle meta-cognitive Telegram commands.

    Commands: /creative, /proactive, /why creative, /meta
    All read-only advisory. No arbitration, no fallback, no writeback.
    """
    import hermes_core

    text = intent.get("raw", "")
    action = intent.get("action", "creative")

    started = time.monotonic()
    log.info(f"[{task_id}] meta_cognitive: {action} | raw='{text[:80]}'")

    try:
        result = hermes_core.handle_meta_cognitive(text, action)
    except Exception as e:
        result = {"status": "failed", "error": str(e)[:500]}

    duration = round(time.monotonic() - started, 3)
    result["duration_s"] = duration
    result["pipeline"] = "meta_cognitive"
    result["action"] = action
    result.setdefault("tool_used", "hermes_meta")
    result.setdefault("tool_fallback", False)

    return result


# ─── MAIN FUNCTION ───────────────────────────────────────────────────────────

def execute(
    intent: dict,
    arb_result: ArbitrationResult,
    context_dict: dict,
    task_id: str = "",
) -> dict:
    """
    Contrato único de ejecución.

    Args:
        intent:       Output de hermes_core.classify()
        arb_result:   Output de arbitration.arbitrate()
        context_dict: Estado del sistema (dict de RiskContext)
        task_id:      ID de la task (para logging y trace)

    Returns:
        dict con al menos:
        {
            "status":       "success" | "failed" | "mcp_delegate",
            "tool_used":    str,
            "tool_fallback": bool,
            "duration_s":   float,
            ... (campos adicionales del executor)
        }
    """
    pipeline = intent.get("pipeline", "system")
    action   = intent.get("action", "answer_question")
    params   = intent.get("params", {})

    log.info(
        f"[{task_id}] execute: {pipeline}.{action} | "
        f"chain={arb_result.fallback_chain} | primary={arb_result.primary_tool}"
    )

    # Meta-cognitive commands — read-only advisory, bypass arbitration
    if pipeline == "meta_cognitive":
        return _execute_meta_cognitive(intent, task_id)

    # 1. Adapt params for each tool in the chain
    adapted_params = _adapt_for_tool(arb_result.primary_tool, pipeline, action, params)

    # 2. Build executor map
    executor_map = _build_executor_map(pipeline, action)

    # Log available executors for this chain
    missing = [t for t in arb_result.fallback_chain if t not in executor_map]
    if missing:
        log.warning(f"[{task_id}] No executor registered for tools: {missing}")

    # 3. Execute with fallback (unified retry + trace)
    started = time.monotonic()
    result  = execute_with_fallback(
        arb_result=arb_result,
        executor_fn=executor_map,
        params=adapted_params,
        task_id=task_id,
        db_path=DB_PATH,
        pipeline=pipeline,
        action=action,
    )
    duration = round(time.monotonic() - started, 3)

    # 4. Enrich result with unified fields
    result["duration_s"]    = duration
    result["pipeline"]      = pipeline
    result["action"]        = action
    result.setdefault("tool_used",     arb_result.primary_tool)
    result.setdefault("tool_fallback", False)

    log.info(
        f"[{task_id}] done: status={result['status']} "
        f"tool={result['tool_used']} "
        f"fallback={result['tool_fallback']} "
        f"duration={duration}s"
    )

    return result


# ─── QUICK TEST ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import dataclasses
    import hermes_core
    from risk_engine import score_intent, RiskContext
    from arbitration import arbitrate

    ctx = RiskContext(
        hernán_online=True,
        chrome_available=False,   # Chrome off → test fallback
        comfyui_available=False,
        deerflow_available=True,
    )
    ctx_dict = dataclasses.asdict(ctx)

    test_cases = [
        "investiga auriculares amazon",
        "estado del sistema",
    ]

    print("=== EXECUTION ORCHESTRATOR TEST ===")
    for text in test_cases:
        intent = hermes_core.classify(text)
        risk   = score_intent(intent, ctx)
        arb    = arbitrate(intent["pipeline"], intent["action"], risk.allowed_tools, ctx_dict)

        print(f"\n[{text}]")
        print(f"  chain={arb.fallback_chain}")

        result = execute(intent, arb, ctx_dict, task_id="TEST-01")
        print(f"  status={result['status']}")
        print(f"  tool={result.get('tool_used')} fallback={result.get('tool_fallback')}")
        print(f"  duration={result.get('duration_s')}s")
        if result["status"] == "failed":
            print(f"  error={result.get('error', '')[:80]}")
        elif result["status"] == "success":
            print(f"  output={str(result)[:120]}")

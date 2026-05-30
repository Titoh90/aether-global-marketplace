"""
HERMES CORE — Intent Parser + Task Router
Usa Ollama qwen2.5:1.5b LOCAL (sin API key, sin costo).
Classifica mensajes Telegram → pipeline + params reales.
NO inventa respuestas. NO filler. Solo routing.
"""
import json
import os
import re
import time
import urllib.request
import urllib.parse
import logging
from pathlib import Path
from typing import Optional

from mediafactory.media_request_router import plan_media_request

log = logging.getLogger("hermes_core")

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")

OLLAMA_URL   = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:1.5b"

# ─── Intent Catalog ────────────────────────────────────────────────────────────
# Maps natural language patterns → pipeline + action
INTENT_PATTERNS = [
    # ── Full content pipeline: research first, then video ──────────────────────
    # More specific than bare "genera video" — must have amazon/producto/afili keyword
    (r"(crea?|genera?|haz|make).*(video|reel|tiktok|contenido).*(amazon|producto|afili)", "content_pipeline", "research_and_create"),
    (r"(crea?|genera?|haz|make).*(amazon|afili).*(video|reel|tiktok|contenido)", "content_pipeline", "research_and_create"),
    (r"video.*afili|afili.*video", "content_pipeline", "research_and_create"),

    # Video pipeline (generic — no research)
    (r"(gen[ea]ra?|crea?|haz|make|create).*(video|clip|reel|tiktok)", "mediafactory", "create_video"),
    (r"video.*(smartwatch|producto|product|amazon|afili)", "mediafactory", "create_video"),

    # Carousel pipeline — before generic image to avoid conflict
    (r"(gen[ea]ra?|crea?|haz|make).*(carousel|carrusel|slides?|diapositiva)", "flow_director", "generate_carousel"),
    (r"(carousel|carrusel)\s+(para|de|of)\s+\w", "flow_director", "generate_carousel"),
    (r"(slides?|carrusel)\s+(de\s+producto|producto)", "flow_director", "generate_carousel"),

    # Image pipeline
    (r"(gen[ea]ra?|crea?|haz).*(imagen|image|foto|photo|pic)", "flow_director", "generate_image"),

    # System status
    (r"(estado|status|qu[eé] (est[aá]|hay|corre|runs?)|cu[aá]nto|how much|check)", "system", "status"),
    (r"(servicios|services|procesos|processes|activo|running|alive)", "system", "status"),

    # Revenue check
    (r"(ingresos|revenue|dinero|money|gané|earned|gan[aó]|plata|cuánto tengo)", "system", "revenue"),

    # Task list
    (r"(tareas|tasks|queue|cola|pendiente|pending)", "system", "tasks"),

    # FLOW: force-run
    (r"(lanza|launch|run|ejecuta|start).*(flow|pipeline|video)", "flow_director", "generate_video"),

    # ComfyUI
    (r"comfy|comfyui|imagen.*local|local.*imagen", "comfy", "generate"),

    # Browser task
    (r"(navega|browse|abre|open|busca en|search in).*(amazon|fiverr|tiktok|web|site)", "browser", "browse"),

    # Research pipeline (DeerFlow / lightweight)
    (r"(investiga|research|analiza|busca|encuentra).*(producto|product|amazon|nicho|niche|trending|viral)", "research", "product_research"),
    (r"(qué|que|cuál|cual).*(producto|vender|trending|viral).*(amazon|tiktok|hoy|semana)", "research", "product_research"),

    # Social posting (standalone — sin generación de video)
    (r"(publica|postea|s[uú]be|upload).*(tiktok)", "social_poster", "post_tiktok"),
    (r"(publica|postea|s[uú]be|upload).*(instagram|ig|reel)", "social_poster", "post_instagram"),
    (r"(publica|postea|s[uú]be|upload).*(video|contenido|clip)", "social_poster", "post"),

    # Email
    (r"(env[íi]a|manda|send|escribe).*(email|correo|mail).*(a\s+\w+|para\s+\w+)", "email", "send_email"),
    (r"(revisa|lee|check).*(email|correo|inbox)", "email", "read_email"),

    # WhatsApp standalone
    (r"(env[íi]a|manda).*(whatsapp|wh?a?ts?|mensaje).*(a\s+\w+|\d{8,})", "whatsapp", "send_message"),

    # File deletion (siempre pide confirmación por risk engine)
    (r"(borra?|elimina?|delete|remove|supprime).*(archivo|file|carpeta|folder|directorio)", "system", "delete_file"),

    # Pause pipeline
    (r"(pausa|pause|detén|stop|silencia|silence).*(hvac|alerts?|alertas?|idle|sys-004)", "system", "pause_pipeline"),

    # ── Meta-Cognitive Commands ──────────────────────────────────────────
    (r"/(weekly)", "meta_cognitive", "weekly"),
    (r"/(digest)", "meta_cognitive", "digest"),
    (r"/(analyze|analizar|analisis|análisis|analysis)", "meta_cognitive", "analyze"),
    (r"/(meta|proactive|creative|why)", "meta_cognitive", "meta"),
    (r"(proactive|proactivo|sugiere|suggest|propon)", "meta_cognitive", "proactive"),
    (r"(meta.cognit|metacognit|cognitive state|estado cognitivo)", "meta_cognitive", "meta"),
    (r"why\s+creative|por.qu[eé].*creative|explica.*creative", "meta_cognitive", "why_creative"),
    (r"(creative|creativo|creatividad)", "meta_cognitive", "creative"),

    # Keyboard button shortcuts
    (r"(estado del sistema|📊)", "system", "status"),
    (r"(cola de tareas|📋)", "system", "tasks"),
    (r"(ingresos reales|💰)", "system", "revenue"),
    (r"(ver traces|📈)", "system", "traces"),
    (r"(qué puedo hacer|❓|ayuda|help|menú|menu|comandos|what can)", "system", "help"),

    # Unknown question → answer with real state
]

# ─── Classifier ───────────────────────────────────────────────────────────────

def classify(text: str) -> dict:
    """
    Returns: {pipeline, action, params, confidence}
    confidence: 'pattern' | 'llm' | 'unknown'
    """
    text_lower = text.lower().strip()

    # 1. Try fast regex patterns first
    for pattern, pipeline, action in INTENT_PATTERNS:
        if re.search(pattern, text_lower):
            if pipeline == "content_pipeline" and action == "research_and_create":
                params = _extract_params(text, pipeline, action)
                log.info(
                    "Intent (pattern): content_pipeline.research_and_create | "
                    "topic='%s' | post=%s",
                    params.get("topic", "")[:50],
                    params.get("post", "false"),
                )
                return {
                    "pipeline": "content_pipeline",
                    "action":   "research_and_create",
                    "params":   params,
                    "confidence": "pattern",
                    "raw": text,
                }

            if pipeline == "mediafactory" and action == "create_video":
                dispatch_plan = plan_media_request(text)
                log.info(
                    "Intent (pattern): %s.%s | worker=%s | backend=%s",
                    dispatch_plan.pipeline,
                    dispatch_plan.action,
                    dispatch_plan.worker,
                    dispatch_plan.model_selection.backend,
                )
                params = dispatch_plan.as_params()
                # Detect post intent — "postealo", "publícalo", "y súbelo", etc.
                post_keywords = r"(post[ae][al]o|publ[ií]ca(lo)?|s[uú]belo|y\s+pub|y\s+post)"
                params["post"] = "true" if re.search(post_keywords, text_lower) else "false"
                params["topic"] = text  # pass original text as topic for executor
                return {
                    "pipeline": dispatch_plan.pipeline,
                    "action": dispatch_plan.action,
                    "params": params,
                    "confidence": "pattern",
                    "raw": text,
                }

            params = _extract_params(text, pipeline, action)
            log.info(f"Intent (pattern): {pipeline}.{action} | params={params}")
            return {
                "pipeline": pipeline,
                "action": action,
                "params": params,
                "confidence": "pattern",
                "raw": text
            }

    # 2. LLM fallback for ambiguous inputs (local, no cost)
    llm_result = _llm_classify(text)
    if llm_result:
        return llm_result

    # 3. Truly unknown → answer with state
    return {
        "pipeline": "system",
        "action": "answer_question",
        "params": {"question": text},
        "confidence": "unknown",
        "raw": text
    }


def _extract_params(text: str, pipeline: str, action: str) -> dict:
    """Extract product name, platform, etc from raw text."""
    params = {}

    # Product/keyword extraction
    product_match = re.search(
        r"(smartwatch|laptop stand|auriculares?|bluetooth|phone|chair|keyboard|mouse|"
        r"[a-zA-Z\s]{3,30})\s*(para|for|de|of)?",
        text, re.IGNORECASE
    )
    if product_match:
        params["product"] = product_match.group(1).strip()

    # Platform
    for plat in ["tiktok", "instagram", "reels", "youtube"]:
        if plat in text.lower():
            params["platform"] = plat
            break
    if "platform" not in params:
        params["platform"] = "tiktok"

    params["product"] = params.get("product", "luxury product")

    # For carousel pipeline: extract product, price, features
    if pipeline == "flow_director" and action == "generate_carousel":
        # "genera carousel para gaming headset $89.99 rating 4.6"
        # Product: text after carousel/carrusel/slides + "para/de/of"
        prod_m = re.search(
            r"(?:carousel|carrusel|slides?)\s+(?:para|de|of)\s+(.+?)(?:\s+\$|\s+precio|\s+price|\s+rating|\s*$)",
            text, re.IGNORECASE
        )
        if prod_m:
            params["product"] = prod_m.group(1).strip()
        else:
            # Fallback: text after verb
            fallback_m = re.search(
                r"(?:gen[ea]ra?|crea?|haz|make)\s+(?:un?\s+)?(?:carousel|carrusel|slides?)\s+(?:de\s+)?(?:para\s+)?(.+?)(?:\s+\$|\s+precio|\s*$)",
                text, re.IGNORECASE
            )
            params["product"] = fallback_m.group(1).strip() if fallback_m else text
        # Price: $XX.XX or XX.XX dolares
        price_m = re.search(r"\$\s*([\d,.]+)", text)
        if price_m:
            params["price"] = f"${price_m.group(1)}"
        # Rating: 4.6/5 or rating 4.6
        rating_m = re.search(r"(?:rating|rated?|★)\s*([\d.]+(?:/\d)?)", text, re.IGNORECASE)
        if rating_m:
            params["rating"] = rating_m.group(1)
        # Slides count: 3 slides / 5 slides
        slides_m = re.search(r"(\d)\s+slides?", text, re.IGNORECASE)
        if slides_m:
            params["slides"] = slides_m.group(1)

    # For research pipeline: pass full raw text as topic
    if pipeline == "research":
        params["topic"] = text
        params["intent"] = text

    # For content_pipeline: extract topic + post flag
    if pipeline == "content_pipeline":
        # Strip verb + "video/reel/contenido [de afiliado] [de/para/sobre]" to get product
        topic_match = re.search(
            r"(?:video|reel|tiktok|contenido)\s+"
            r"(?:de\s+afiliado\s+de\s+|de\s+afiliado\s+|afiliado\s+de\s+)?"
            r"(?:de\s+|sobre\s+|para\s+|del?\s+)?"
            r"(.+?)(?:\s+y\s+(?:p[oó]st|pub|s[uú]b)|\s+y\s+|\s+amazon|\s+afili|\s*$)",
            text, re.IGNORECASE
        )
        params["topic"] = topic_match.group(1).strip() if topic_match else text
        post_kw = r"(post[ae][al]o|publ[ií]ca(lo)?|s[uú]belo|y\s+pub|y\s+post)"
        params["post"] = "true" if re.search(post_kw, text.lower()) else "false"
        params["intent"] = text

    return params


def _llm_classify(text: str) -> Optional[dict]:
    """Ask local Ollama to classify when regex doesn't match."""
    prompt = f"""Classify this message into one of these pipelines:
- flow_director (generate video or image content)
- system (check status, revenue, tasks)
- browser (navigate web, search Amazon)
- unknown

Message: "{text}"

Reply with ONLY valid JSON like: {{"pipeline": "X", "action": "Y", "params": {{}}}}
No explanation."""

    try:
        data = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 100}
        }).encode()

        req = urllib.request.Request(
            OLLAMA_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            result = json.loads(resp.read())
            raw_response = result.get("response", "").strip()

            # Extract JSON from response
            match = re.search(r'\{[^}]+\}', raw_response)
            if match:
                parsed = json.loads(match.group())
                parsed["confidence"] = "llm"
                parsed["raw"] = text
                parsed.setdefault("params", {})
                log.info(f"Intent (LLM): {parsed}")
                return parsed
    except Exception as e:
        log.warning(f"LLM classify failed: {e}")

    return None


# ─── System State Reader (returns REAL data only) ─────────────────────────────

def get_real_status() -> dict:
    """Read actual running state. No hallucinations."""
    import socket
    import sqlite3

    status = {
        "services": {},
        "revenue_today_usd": 0,
        "tasks_queued": 0,
        "tasks_running": 0,
        "chrome_cdp_active": False,
        "ollama_models": [],
        "comfyui_active": False,
        "browser_use_available": True,
    }

    # Check services via port
    checks = {
        "ollama": 11434,
        "comfyui": 8188,
        "openclaw": 18789,
        "claude_mem": 37777,
        "dashboard": 8090,
    }
    for name, port in checks.items():
        try:
            s = socket.create_connection(("127.0.0.1", port), timeout=1)
            s.close()
            status["services"][name] = "✅"
        except:
            status["services"][name] = "❌"

    # Chrome CDP
    try:
        s = socket.create_connection(("127.0.0.1", 9222), timeout=1)
        s.close()
        status["chrome_cdp_active"] = True
    except:
        status["chrome_cdp_active"] = False

    # Ollama models
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as r:
            d = json.loads(r.read())
            status["ollama_models"] = [m["name"] for m in d.get("models", [])]
    except:
        pass

    # Real revenue (from tasks DB)
    db_path = IMPERIO_ROOT / "operator" / "tasks.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            today = __import__("datetime").date.today().isoformat()
            row = conn.execute(
                "SELECT COALESCE(SUM(amount_usd),0) FROM revenue_log WHERE logged_at LIKE ?",
                (today + "%",)
            ).fetchone()
            status["revenue_today_usd"] = row[0] if row else 0

            row2 = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status='queued'"
            ).fetchone()
            status["tasks_queued"] = row2[0] if row2 else 0

            row3 = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status='running'"
            ).fetchone()
            status["tasks_running"] = row3[0] if row3 else 0
            conn.close()
        except:
            pass

    return status


def format_status(s: dict) -> str:
    """Format real status as Telegram message."""
    svcs = s["services"]
    lines = [
        "📊 *ESTADO REAL — IMPERIO*",
        "",
        "*Servicios:*",
        f"  Ollama: {svcs.get('ollama','❓')} | ComfyUI: {svcs.get('comfyui','❓')}",
        f"  OpenClaw: {svcs.get('openclaw','❓')} | Dashboard: {svcs.get('dashboard','❓')}",
        f"  Chrome CDP: {'✅ activo' if s['chrome_cdp_active'] else '❌ inactivo (necesario para Flow)'}",
        "",
        f"*Modelos Ollama:* {', '.join(s['ollama_models']) or 'ninguno'}",
        "",
        f"*Tasks:* {s['tasks_queued']} en cola | {s['tasks_running']} corriendo",
        f"*Revenue hoy:* ${s['revenue_today_usd']:.2f} USD",
    ]
    return "\n".join(lines)


# ── Meta-Cognitive Command Handlers ────────────────────────────────────────────
# Read-only advisory. Never mutates production pipeline.

def handle_meta_cognitive(text: str, action: str) -> dict:
    """
    Route meta-cognitive Telegram commands to HermesMetaOrchestrator.

    Actions:
      /creative          → full creative cycle output
      /proactive         → proactive suggestions
      /why creative <X>  → product diagnosis
      /meta              → full meta-cognitive state
    """
    try:
        from core.meta_cognitive.orchestrator import HermesMetaOrchestrator
        orchestrator = HermesMetaOrchestrator()

        if action == "creative":
            try:
                from core.creative_intelligence.creative_loop_cycle import run_creative_cycle
                output = run_creative_cycle(persist=False)
                formatted = output.format_for_telegram()
            except Exception:
                from core.creative_intelligence.proactive_brain import ProactiveBrain
                formatted = ProactiveBrain().format_brand_creative_report()
            return {"status": "success", "formatted": formatted}

        elif action == "proactive":
            try:
                output = orchestrator.run_cycle(persist=True)
                formatted = orchestrator.format_proactive(output)
            except Exception:
                from core.creative_intelligence.proactive_brain import ProactiveBrain
                from core.creative_intelligence.creative_loop_cycle import run_creative_cycle
                cycle = run_creative_cycle(persist=False)
                formatted = cycle.format_for_telegram()
            return {"status": "success", "formatted": formatted}

        elif action == "why_creative":
            # Extract product name/asin from text
            product_query = text.replace("/why creative", "").replace("why creative", "").strip()
            try:
                formatted = orchestrator.format_why_creative(product_query if product_query else "")
            except Exception:
                from core.creative_intelligence.proactive_brain import ProactiveBrain
                formatted = ProactiveBrain().format_product_diagnosis(product_query if product_query else "")
            return {"status": "success", "formatted": formatted}

        elif action == "meta":
            output = orchestrator.run_cycle(persist=True)
            formatted = orchestrator.format_meta_state(output)
            return {"status": "success", "formatted": formatted}

        elif action == "digest":
            output = orchestrator.run_cycle(persist=True)
            date_str = time.strftime("%A %d %B %Y")
            header = f"☀️ *Daily Creative Digest* — {date_str}\n\n"
            formatted = header + output.format_for_telegram()
            return {"status": "success", "formatted": formatted}

        elif action == "weekly":
            return handle_weekly_digest()

        elif action == "analyze":
            return handle_analyze()

        # Fallback to creative
        try:
            from core.creative_intelligence.creative_loop_cycle import run_creative_cycle
            output = run_creative_cycle(persist=False)
            formatted = output.format_for_telegram()
        except Exception:
            formatted = "Creative intelligence module unavailable."
        return {"status": "success", "formatted": formatted}

    except ImportError as e:
        return {"status": "failed", "error": f"Meta-cognitive module unavailable: {e}"}
    except Exception as e:
        return {"status": "failed", "error": str(e)[:500]}


def handle_analyze() -> dict:
    """
    Run LLM-enriched meta-cognitive analysis.

    Runs a fresh deterministic cycle via HermesMetaOrchestrator, then enriches
    the output with LLM narrative analysis using the Hermes Meta Orchestrator
    system prompt. Falls back to deterministic output if LLM is unavailable.

    Feature-flagged via FEATURE_LLM_ANALYSIS (default: disabled).
    """
    import asyncio

    if os.environ.get("FEATURE_LLM_ANALYSIS", "0") != "1":
        return {
            "status": "failed",
            "error": (
                "🧠 LLM analysis está desactivado.\n"
                "Para activarlo: export FEATURE_LLM_ANALYSIS=1\n"
                "Usa /digest o /meta para el análisis determinista."
            ),
        }

    try:
        from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

        orchestrator = HermesMetaOrchestrator()

        # Run a fresh deterministic cycle first
        output = orchestrator.run_cycle(persist=True)

        # Enrich with LLM analysis (run async in sync context)
        formatted = asyncio.run(orchestrator.enrich_with_llm(output))

        return {"status": "success", "formatted": formatted}

    except ImportError as e:
        return {
            "status": "failed",
            "error": f"Meta-cognitive module unavailable: {e}",
        }
    except Exception as e:
        return {"status": "failed", "error": str(e)[:500]}


def handle_weekly_digest() -> dict:
    """
    Generate weekly creative summary from last 7 days of meta_cognitive_log.json.
    Triggered by /weekly command.
    Uses shared HermesMetaOrchestrator.build_weekly_summary().
    """
    from core.meta_cognitive.orchestrator import HermesMetaOrchestrator

    log_file = IMPERIO_ROOT / "REVENUE" / "meta_cognitive_log.json"

    if not log_file.exists():
        return {"status": "failed", "error": "No meta-cognitive log found. Run a cycle first."}

    try:
        data = json.loads(log_file.read_text())
        if not isinstance(data, list) or not data:
            return {"status": "failed", "error": "Log is empty."}

        # Filter to last 7 days
        cutoff = time.time() - 604800
        week_cycles = []
        for d in data:
            if not isinstance(d, dict):
                continue
            ts_str = d.get("timestamp", d.get("generated_at", ""))
            try:
                ts = time.mktime(time.strptime(ts_str[:19], "%Y-%m-%dT%H:%M:%S"))
            except Exception:
                continue
            if ts >= cutoff:
                week_cycles.append(d)

        if not week_cycles:
            return {"status": "failed", "error": "No cycles in last 7 days."}

        # Use shared summary builder
        summary = HermesMetaOrchestrator.build_weekly_summary(week_cycles)
        date_str = time.strftime("%d %B %Y")
        header = f"📊 *Weekly Creative Summary* — {date_str}\n\n"
        formatted = header + summary

        return {"status": "success", "formatted": formatted}

    except Exception as e:
        return {"status": "failed", "error": str(e)[:500]}

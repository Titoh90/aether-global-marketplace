#!/usr/bin/env python3
"""
JARVIS BRAIN v1.0 — Cerebro Autónomo de IMPERIO
=================================================
Reemplaza la dependencia de Claude/Antigravity con modelos GRATUITOS:
  - Llama 3.3 70B via Nvidia NIM (principal)
  - Llama 3.3 70B via OpenRouter free tier (fallback)
  - qwen2.5:7b via Ollama local (fallback offline)

CARACTERÍSTICAS:
  - Conversación natural en Telegram (entiende lenguaje natural)
  - Memoria persistente de sesión (SQLite)
  - Planificación: propone próxima acción tras cada tarea
  - Auto-optimización: analiza resultados y sugiere mejoras
  - Routing inteligente de tasks → execution_orchestrator
  - Funciona 24/7 sin intervención humana

USO:
  python3 jarvis_brain.py --mode chat      # Responde mensajes Telegram
  python3 jarvis_brain.py --mode plan      # Genera plan diario autónomo
  python3 jarvis_brain.py --mode optimize  # Analiza resultados y optimiza
"""

import json
import logging
import os
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ─── Rutas ────────────────────────────────────────────────────────────────────
OPERATOR_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator")
NUCLEO_ROOT   = Path("/Users/minimacm4/IMPERIO_NUCLEO")
DB_PATH       = OPERATOR_ROOT / "tasks.db"
BRAIN_DB      = OPERATOR_ROOT / "jarvis_memory.db"
LOG_PATH      = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/logs/jarvis_brain.log")

LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [JARVIS] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("jarvis_brain")

# ─── Cargar .env ──────────────────────────────────────────────────────────────
def _load_env():
    for env_file in [NUCLEO_ROOT / ".env", Path.home() / ".env"]:
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"'))

_load_env()

# ─── API Config ───────────────────────────────────────────────────────────────
NIM_BASE    = "https://integrate.api.nvidia.com/v1"
NIM_KEY     = os.getenv("NVIDIA_NIM_API_KEY", "")
OR_BASE     = "https://openrouter.ai/api/v1"
OR_KEY      = os.getenv("OPENROUTER_API_KEY", "")
OLLAMA_BASE = "http://localhost:11434/api"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "5403253763")

# Modelo principal: Llama 3.3 70B via NIM (gratis con tu nvapi key)
PRIMARY_MODEL   = "meta/llama-3.3-70b-instruct"
FALLBACK_MODEL  = "meta-llama/llama-3.3-70b-instruct:free"
OFFLINE_MODEL   = "qwen2.5:7b"

# ─── Memoria SQLite ───────────────────────────────────────────────────────────
def init_memory_db():
    """Crear tablas de memoria persistente del cerebro."""
    conn = sqlite3.connect(BRAIN_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tokens_used INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jarvis_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS optimizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT DEFAULT (datetime('now')),
            task_type TEXT,
            result TEXT,
            suggestion TEXT,
            applied INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

def save_message(role: str, content: str, tokens: int = 0):
    conn = sqlite3.connect(BRAIN_DB)
    conn.execute(
        "INSERT INTO conversations (role, content, tokens_used) VALUES (?,?,?)",
        (role, content, tokens)
    )
    conn.commit()
    conn.close()

def get_recent_context(n: int = 10) -> list[dict]:
    """Obtener las últimas N interacciones para contexto."""
    conn = sqlite3.connect(BRAIN_DB)
    rows = conn.execute(
        "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?", (n,)
    ).fetchall()
    conn.close()
    # Invertir para orden cronológico
    return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

def set_state(key: str, value: str):
    conn = sqlite3.connect(BRAIN_DB)
    conn.execute(
        "INSERT OR REPLACE INTO jarvis_state (key, value, updated_at) VALUES (?,?,datetime('now'))",
        (key, value)
    )
    conn.commit()
    conn.close()

def get_state(key: str) -> str | None:
    conn = sqlite3.connect(BRAIN_DB)
    row = conn.execute("SELECT value FROM jarvis_state WHERE key=?", (key,)).fetchone()
    conn.close()
    return row[0] if row else None

# ─── LLM Client ───────────────────────────────────────────────────────────────

def _call_openai_api(base_url: str, api_key: str, model: str,
                     messages: list[dict], max_tokens: int = 1024,
                     temperature: float = 0.7) -> str | None:
    """Call any OpenAI-compatible API endpoint."""
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode()

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        log.warning(f"  HTTP {e.code} from {base_url}: {body}")
        return None
    except Exception as e:
        log.warning(f"  API error ({base_url}): {e}")
        return None


def _call_ollama(model: str, messages: list[dict], max_tokens: int = 1024) -> str | None:
    """Call local Ollama API (offline fallback)."""
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.7}
    }).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/chat",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
            return data.get("message", {}).get("content")
    except Exception as e:
        log.warning(f"  Ollama error: {e}")
        return None


def think(messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
    """
    Cerebro principal con cascada de fallbacks:
    NIM (70B) → OpenRouter free (70B) → Ollama local (7B)
    """
    # 1. Nvidia NIM — Llama 3.3 70B (tu nvapi key)
    response = _call_openai_api(NIM_BASE, NIM_KEY, PRIMARY_MODEL, messages, max_tokens, temperature)
    if response:
        log.info(f"  ✓ NIM responded ({len(response)} chars)")
        return response

    log.info("  NIM unavailable → trying OpenRouter...")

    # 2. OpenRouter — Llama 3.3 70B free tier
    response = _call_openai_api(OR_BASE, OR_KEY, FALLBACK_MODEL, messages, max_tokens, temperature)
    if response:
        log.info(f"  ✓ OpenRouter responded ({len(response)} chars)")
        return response

    log.info("  OpenRouter unavailable → trying Ollama local...")

    # 3. Ollama local — sin internet requerido
    response = _call_ollama(OFFLINE_MODEL, messages, max_tokens)
    if response:
        log.info(f"  ✓ Ollama responded ({len(response)} chars)")
        return response

    log.error("  ALL LLM backends failed")
    return "⚠️ JARVIS sin conexión: todos los backends LLM fallaron. Verifica conexión a internet u Ollama."

# ─── Sistema Prompt de JARVIS ─────────────────────────────────────────────────

JARVIS_SYSTEM = """Eres JARVIS, el agente autónomo de IMPERIO — el sistema de generación de ingresos pasivos de Hernán.

IDENTIDAD:
- Nombre: JARVIS (Just A Rather Very Intelligent System)
- Propietario: Hernán
- Objetivo: Generar ingresos vía Amazon Affiliate Marketing en TikTok/Instagram
- Cuenta afiliado: aetherglobal-20 | TikTok: @alexanderaether

PERSONALIDAD:
- Directo, conciso, nunca genérico
- Reportas estado REAL del sistema
- Propones la SIGUIENTE acción después de cada tarea
- Piensas en revenue: cada decisión se evalúa por impacto en conversiones

CAPACIDADES REALES (las que tienes instaladas y funcionando):
1. Investigar productos Amazon (DeerFlow + Llama 3.3 70B via NIM)
2. Generar videos cortos con voiceover (Chatterbox TTS + Pexels + FFmpeg)
3. Crear carousels de imágenes (Google Flow / Nano Banana — gratis)
4. Navegar internet como humano (Playwright + Chrome CDP)
5. Publicar en TikTok e Instagram (vía social_poster.py)
6. Enviar mensajes WhatsApp (whatsapp_executor.py)
7. Analizar nichos y tendencias (DeerFlow research)
8. Clonar voces (Applio RVC) — disponible pero no en pipeline aún
9. Generar imágenes SDXL (Fooocus) — disponible pero no en pipeline aún

REGLAS:
- NO inventes datos de revenue que no existen en tasks.db
- NO simules tareas completadas — reporta estado real
- Si una tarea falla, reportas el error real y propones fix
- Cuando el usuario pide algo ambiguo, preguntas UNA sola pregunta clave
- Siempre terminas con: "¿Procedo?" o "Próxima acción recomendada: [X]"

FORMATO DE RESPUESTAS TELEGRAM:
- Corto y claro (máx 3-4 párrafos)
- Usa emojis para estado: ✅ éxito, ❌ error, ⚠️ advertencia, 🔄 en progreso
- Código inline en `backticks` cuando mencionas comandos
"""

# ─── Telegram ─────────────────────────────────────────────────────────────────

def send_telegram(text: str, chat_id: str = None) -> bool:
    """Enviar mensaje a Telegram."""
    if not TELEGRAM_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN not set — cannot send message")
        return False
    chat_id = chat_id or TELEGRAM_CHAT
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as e:
        log.warning(f"Telegram send failed: {e}")
        return False

# ─── Análisis de Tareas del Sistema ───────────────────────────────────────────

def get_system_status() -> str:
    """Obtener estado real del sistema desde tasks.db"""
    try:
        conn = sqlite3.connect(DB_PATH)
        # Tareas recientes
        recent = conn.execute("""
            SELECT status, COUNT(*) as cnt
            FROM tasks
            GROUP BY status
        """).fetchall()

        # Revenue
        rev_rows = conn.execute("""
            SELECT amount, currency, note, created_at
            FROM revenue_log
            ORDER BY created_at DESC
            LIMIT 5
        """).fetchall() if _table_exists(conn, "revenue_log") else []

        # Última tarea
        last_task = conn.execute("""
            SELECT task_type, status, created_at, result_summary
            FROM tasks
            ORDER BY created_at DESC LIMIT 1
        """).fetchone()

        conn.close()

        status_parts = []
        if recent:
            status_str = " | ".join(f"{s}:{c}" for s,c in recent)
            status_parts.append(f"Tasks: {status_str}")
        if last_task:
            status_parts.append(f"Última tarea: {last_task[0]} ({last_task[1]}) @ {last_task[2][:16]}")
        if rev_rows:
            total = sum(r[0] for r in rev_rows if r[0])
            status_parts.append(f"Revenue reciente: ${total:.2f}")

        return "\n".join(status_parts) if status_parts else "Sin datos en tasks.db aún"
    except Exception as e:
        return f"Error leyendo tasks.db: {e}"

def _table_exists(conn, table_name: str) -> bool:
    result = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
    ).fetchone()
    return result is not None

# ─── Chat Mode: Responde mensajes de Telegram ─────────────────────────────────

def chat(user_message: str, user_name: str = "Hernán") -> str:
    """
    Procesar un mensaje de usuario y generar respuesta inteligente.
    Mantiene contexto de conversación en memoria.
    """
    log.info(f"Chat from {user_name}: {user_message[:80]}...")

    # Guardar mensaje del usuario
    save_message("user", user_message)

    # Construir contexto
    history = get_recent_context(n=8)
    system_status = get_system_status()

    messages = [
        {"role": "system", "content": JARVIS_SYSTEM + f"\n\nESTADO ACTUAL DEL SISTEMA:\n{system_status}"},
    ] + history

    # Generar respuesta
    response = think(messages, max_tokens=512, temperature=0.7)
    save_message("assistant", response)

    log.info(f"JARVIS response: {response[:100]}...")
    return response

# ─── Plan Mode: Genera plan diario autónomo ───────────────────────────────────

def generate_daily_plan() -> dict:
    """
    Genera el plan de trabajo autónomo para hoy.
    Llama al LLM para decidir: qué productos investigar, cuántos videos crear, etc.
    """
    log.info("Generating autonomous daily plan...")

    # Contexto del sistema
    system_status = get_system_status()
    yesterday_plan = get_state("last_plan") or "Sin plan previo"

    messages = [
        {"role": "system", "content": JARVIS_SYSTEM},
        {"role": "user", "content": f"""Genera el plan de trabajo de HOY para maximizar revenue de afiliados Amazon.

ESTADO DEL SISTEMA:
{system_status}

PLAN DE AYER:
{yesterday_plan}

GENERA UN PLAN JSON con este formato exacto:
{{
  "hora_inicio": "07:00",
  "productos_a_investigar": ["producto1", "producto2"],
  "videos_a_crear": 2,
  "tipo_contenido": "pixelle_video",
  "nichos_prioritarios": ["tech", "gaming", "lifestyle"],
  "objetivo_del_dia": "descripción corta",
  "acciones": [
    {{"hora": "07:00", "accion": "research", "params": {{"product": "producto1"}}}},
    {{"hora": "08:00", "accion": "content_pipeline", "params": {{"product": "producto1", "platform": "tiktok"}}}}
  ]
}}

Solo responde con el JSON, sin explicación."""}
    ]

    response = think(messages, max_tokens=800, temperature=0.3)

    # Intentar parsear JSON
    try:
        # Extraer JSON del response (puede haber texto extra)
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            plan = json.loads(response[start:end])
        else:
            plan = {"error": "No JSON in response", "raw": response}
    except json.JSONDecodeError as e:
        plan = {"error": str(e), "raw": response[:200]}

    # Guardar plan
    set_state("last_plan", json.dumps(plan, ensure_ascii=False))
    set_state("plan_date", datetime.now().strftime("%Y-%m-%d"))

    log.info(f"Daily plan generated: {json.dumps(plan, ensure_ascii=False)[:200]}")
    return plan

# ─── Optimize Mode: Analiza resultados y sugiere mejoras ──────────────────────

def analyze_and_optimize() -> str:
    """
    Analiza los resultados recientes y genera sugerencias de optimización.
    Se ejecuta después de cada tarea completada.
    """
    log.info("Running self-optimization analysis...")

    system_status = get_system_status()
    recent_context = get_recent_context(n=5)

    messages = [
        {"role": "system", "content": JARVIS_SYSTEM},
        {"role": "user", "content": f"""Analiza el estado actual del sistema IMPERIO y sugiere mejoras específicas.

ESTADO:
{system_status}

CONTEXTO RECIENTE:
{json.dumps(recent_context, ensure_ascii=False, indent=2)}

Responde con:
1. QUÉ está funcionando bien (máx 2 puntos)
2. QUÉ necesita mejora INMEDIATA (máx 2 puntos)
3. PRÓXIMA ACCIÓN RECOMENDADA (1 acción específica)

Sé brutalmente honesto y específico. No inventas métricas."""}
    ]

    analysis = think(messages, max_tokens=400, temperature=0.4)

    # Guardar optimización en DB
    conn = sqlite3.connect(BRAIN_DB)
    conn.execute(
        "INSERT INTO optimizations (task_type, result, suggestion) VALUES (?,?,?)",
        ("self_analysis", system_status[:200], analysis[:500])
    )
    conn.commit()
    conn.close()

    log.info(f"Optimization analysis: {analysis[:150]}...")
    return analysis

# ─── Health Check ─────────────────────────────────────────────────────────────

def health_check() -> dict:
    """Verifica que todos los backends LLM estén disponibles."""
    results = {}

    # NIM
    test_msg = [{"role": "user", "content": "Di solo: OK"}]
    resp = _call_openai_api(NIM_BASE, NIM_KEY, PRIMARY_MODEL, test_msg, max_tokens=5, temperature=0)
    results["nvidia_nim"] = "✅" if resp else "❌"

    # OpenRouter
    resp = _call_openai_api(OR_BASE, OR_KEY, FALLBACK_MODEL, test_msg, max_tokens=5, temperature=0)
    results["openrouter"] = "✅" if resp else "❌"

    # Ollama
    resp = _call_ollama(OFFLINE_MODEL, test_msg, max_tokens=5)
    results["ollama_local"] = "✅" if resp else "❌"

    # Telegram
    results["telegram_token"] = "✅" if TELEGRAM_TOKEN else "❌"

    # tasks.db
    results["tasks_db"] = "✅" if DB_PATH.exists() else "❌"

    log.info(f"Health check: {results}")
    return results

# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser(description="JARVIS Brain — Autonomous AI for IMPERIO")
    ap.add_argument("--mode", choices=["chat", "plan", "optimize", "health", "interactive"],
                    default="health", help="Operation mode")
    ap.add_argument("--message", default="", help="Message for chat mode")
    ap.add_argument("--notify", action="store_true", help="Send result to Telegram")
    args = ap.parse_args()

    init_memory_db()
    log.info(f"JARVIS Brain starting — mode: {args.mode}")

    if args.mode == "health":
        results = health_check()
        print("\n=== JARVIS Health Check ===")
        for k, v in results.items():
            print(f"  {v} {k}")
        overall = "ALL SYSTEMS GO 🚀" if all(v == "✅" for v in results.values()) else "DEGRADED ⚠️"
        print(f"\nStatus: {overall}")

    elif args.mode == "chat":
        if not args.message:
            print("Error: --message required for chat mode")
            return
        response = chat(args.message)
        print(f"\nJARVIS: {response}")
        if args.notify:
            send_telegram(response)

    elif args.mode == "plan":
        plan = generate_daily_plan()
        print("\n=== Daily Plan ===")
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        if args.notify and "error" not in plan:
            msg = "📋 *Plan del día — JARVIS*\n\n"
            msg += f"🎯 {plan.get('objetivo_del_dia', 'Sin objetivo')}\n"
            msg += f"🔍 Productos: {', '.join(plan.get('productos_a_investigar', []))}\n"
            msg += f"🎬 Videos: {plan.get('videos_a_crear', 0)}\n"
            msg += f"⏰ Inicio: {plan.get('hora_inicio', '07:00')}"
            send_telegram(msg)

    elif args.mode == "optimize":
        analysis = analyze_and_optimize()
        print("\n=== Self-Optimization Analysis ===")
        print(analysis)
        if args.notify:
            send_telegram(f"🧠 *JARVIS Auto-Análisis*\n\n{analysis}")

    elif args.mode == "interactive":
        print("JARVIS Interactive Mode — escribe 'exit' para salir")
        init_memory_db()
        while True:
            try:
                user_input = input("\nTú: ").strip()
                if user_input.lower() in ("exit", "quit", "salir"):
                    break
                if not user_input:
                    continue
                response = chat(user_input)
                print(f"\nJARVIS: {response}")
            except KeyboardInterrupt:
                break
        print("\nJARVIS offline.")

if __name__ == "__main__":
    main()

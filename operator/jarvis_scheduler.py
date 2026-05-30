#!/usr/bin/env python3
"""
JARVIS SCHEDULER v1.0 — Pipeline Diario Autónomo
==================================================
Ejecuta el pipeline de revenue todos los días de manera autónoma.
No requiere intervención humana. Reporta resultados por Telegram.

FLUJO DIARIO (7:00 AM por defecto):
  1. JARVIS decide qué productos investigar hoy (LLM plan)
  2. Research de productos Amazon (DeerFlow/NIM)
  3. Generación de 2-3 videos (MediaFactory/Pixelle)
  4. Envía videos a Telegram para revisión
  5. Post-análisis: JARVIS reflexiona sobre resultados

USO:
  python3 jarvis_scheduler.py              # Correr pipeline ahora
  python3 jarvis_scheduler.py --dry-run    # Simular sin ejecutar
  python3 jarvis_scheduler.py --status     # Ver estado del último run
"""

import json
import logging
import os
import subprocess
import sys
import time
import sqlite3
import urllib.request
from datetime import datetime, date
from pathlib import Path

# ─── Rutas ────────────────────────────────────────────────────────────────────
OPERATOR_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator")
REVENUE_ROOT  = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE")
NUCLEO_ROOT   = Path("/Users/minimacm4/IMPERIO_NUCLEO")
SCHED_DB      = OPERATOR_ROOT / "scheduler_state.db"
LOG_DIR       = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/logs")
LOG_PATH      = LOG_DIR / "jarvis_scheduler.log"

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SCHED] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("jarvis_scheduler")

# Añadir operator root al path
sys.path.insert(0, str(OPERATOR_ROOT))

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
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.getenv("TELEGRAM_CHAT_ID", "5403253763")
PYTHON         = sys.executable  # Usar el Python actual

# ─── Estado del Scheduler ─────────────────────────────────────────────────────
def init_sched_db():
    conn = sqlite3.connect(SCHED_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduler_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            started_at TEXT DEFAULT (datetime('now')),
            finished_at TEXT,
            status TEXT DEFAULT 'running',
            plan TEXT,
            products_researched INTEGER DEFAULT 0,
            videos_created INTEGER DEFAULT 0,
            errors TEXT
        )
    """)
    conn.commit()
    conn.close()

def start_run(plan: dict) -> int:
    conn = sqlite3.connect(SCHED_DB)
    cur = conn.execute(
        "INSERT INTO scheduler_runs (run_date, plan) VALUES (?,?)",
        (date.today().isoformat(), json.dumps(plan, ensure_ascii=False))
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id

def update_run(run_id: int, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [run_id]
    conn = sqlite3.connect(SCHED_DB)
    conn.execute(f"UPDATE scheduler_runs SET {fields} WHERE id=?", values)
    conn.commit()
    conn.close()

def get_last_run() -> dict | None:
    conn = sqlite3.connect(SCHED_DB)
    row = conn.execute(
        "SELECT * FROM scheduler_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return None
    cols = ["id","run_date","started_at","finished_at","status","plan",
            "products_researched","videos_created","errors"]
    return dict(zip(cols, row))

# ─── Telegram ─────────────────────────────────────────────────────────────────
def notify(text: str) -> bool:
    if not TELEGRAM_TOKEN:
        log.warning("No TELEGRAM_BOT_TOKEN — skipping notification")
        return False
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT,
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
        log.warning(f"Telegram notify failed: {e}")
        return False

# ─── Paso 1: Obtener Plan del Día ─────────────────────────────────────────────
def get_daily_plan() -> dict:
    """Obtener plan del día desde jarvis_brain.py"""
    log.info("Step 1: Getting daily plan from JARVIS Brain...")
    brain_script = OPERATOR_ROOT / "jarvis_brain.py"

    if not brain_script.exists():
        log.warning("jarvis_brain.py not found — using default plan")
        return {
            "productos_a_investigar": ["gaming headset", "bluetooth speaker"],
            "videos_a_crear": 2,
            "tipo_contenido": "content_pipeline",
            "nichos_prioritarios": ["tech", "gaming"],
            "objetivo_del_dia": "Generar 2 videos de afiliados tech"
        }

    try:
        result = subprocess.run(
            [PYTHON, str(brain_script), "--mode", "plan"],
            capture_output=True, text=True, timeout=120,
            cwd=str(OPERATOR_ROOT)
        )
        # Extraer JSON del output
        output = result.stdout
        start = output.find("{")
        end = output.rfind("}") + 1
        if start >= 0 and end > start:
            plan = json.loads(output[start:end])
            log.info(f"Plan received: {json.dumps(plan, ensure_ascii=False)[:200]}")
            return plan
        else:
            log.warning(f"No JSON in plan output: {output[:200]}")
    except Exception as e:
        log.error(f"Plan generation failed: {e}")

    return {
        "productos_a_investigar": ["wireless earbuds", "gaming mouse"],
        "videos_a_crear": 2,
        "tipo_contenido": "content_pipeline",
        "objetivo_del_dia": "Pipeline por defecto (plan LLM falló)"
    }

# ─── Paso 2: Research de Productos ────────────────────────────────────────────
def research_products(products: list[str], dry_run: bool = False) -> list[dict]:
    """Investigar cada producto via research_executor."""
    results = []
    log.info(f"Step 2: Researching {len(products)} products...")

    if dry_run:
        log.info("[DRY RUN] Skipping actual research")
        return [{"product": p, "status": "dry_run", "brief": f"Brief simulado para {p}"} for p in products]

    try:
        # Importar research_executor del operador
        from executors.research_executor import run_research

        for product in products:
            log.info(f"  Researching: {product}")
            try:
                result = run_research({"product": product, "platform": "amazon"}, f"sched_{int(time.time())}")
                results.append({"product": product, "status": "success", "data": result})
                log.info(f"  ✓ Research OK for {product}")
                time.sleep(5)  # Pausa entre researches
            except Exception as e:
                log.error(f"  Research failed for {product}: {e}")
                results.append({"product": product, "status": "failed", "error": str(e)})

    except ImportError as e:
        log.error(f"Cannot import research_executor: {e}")
        # Fallback: llamar via subprocess
        for product in products:
            results.append({"product": product, "status": "import_error"})

    return results

# ─── Paso 3: Crear Videos ─────────────────────────────────────────────────────
def create_content(products: list[str], n_videos: int, dry_run: bool = False) -> list[str]:
    """Crear videos via content_pipeline_executor."""
    created = []
    log.info(f"Step 3: Creating {n_videos} videos...")

    if dry_run:
        log.info("[DRY RUN] Skipping video creation")
        return [f"/tmp/dry_run_video_{i}.mp4" for i in range(n_videos)]

    try:
        from executors.content_pipeline_executor import run_content_pipeline

        for i, product in enumerate(products[:n_videos]):
            log.info(f"  Creating video {i+1}/{n_videos}: {product}")
            try:
                task_id = f"sched_{int(time.time())}_{i}"
                result = run_content_pipeline(
                    {"product": product, "platform": "tiktok", "style": "affiliate"},
                    task_id
                )
                if result.get("status") == "success":
                    video_path = result.get("output_path", "")
                    created.append(video_path)
                    log.info(f"  ✓ Video created: {video_path}")
                else:
                    log.error(f"  Pipeline failed for {product}: {result.get('error','')}")
            except Exception as e:
                log.error(f"  Video creation failed for {product}: {e}")

            time.sleep(10)  # Pausa entre videos (GPU memory)

    except ImportError as e:
        log.error(f"Cannot import content_pipeline_executor: {e}")
        # Intentar via subprocess
        for i, product in enumerate(products[:n_videos]):
            try:
                gateway = NUCLEO_ROOT / "interfaces/imperio_operator_gateway.py"
                log.info(f"  Triggering via gateway subprocess for: {product}")
                # Solo hacer log — el gateway ya está corriendo
                log.info(f"  [MANUAL] Send Telegram: 'crea video de {product}'")
            except Exception as e2:
                log.error(f"  Subprocess also failed: {e2}")

    return created

# ─── Paso 4: Notificar Resultados ─────────────────────────────────────────────
def send_daily_summary(plan: dict, research_results: list, videos: list, elapsed: float):
    """Enviar resumen completo a Telegram."""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    ok_research = sum(1 for r in research_results if r.get("status") == "success")
    total_research = len(research_results)

    msg = f"""🤖 *JARVIS — Reporte Diario*
📅 {today} | ⏱ {elapsed:.0f}s

🎯 *Objetivo:* {plan.get('objetivo_del_dia', 'N/A')}

📊 *Resultados:*
• 🔍 Research: {ok_research}/{total_research} productos
• 🎬 Videos: {len(videos)} creados
• 🏆 Nichos: {', '.join(plan.get('nichos_prioritarios', [])[:3])}

{'✅ Pipeline completado' if videos else '⚠️ Sin videos creados — revisar logs'}

📋 Log: `/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/logs/jarvis_scheduler.log`"""

    notify(msg)

# ─── Paso 5: Auto-análisis Post-Pipeline ──────────────────────────────────────
def run_post_analysis(dry_run: bool = False):
    """Ejecutar análisis de optimización tras el pipeline."""
    log.info("Step 5: Running post-pipeline self-optimization...")
    if dry_run:
        log.info("[DRY RUN] Skipping optimization")
        return

    brain_script = OPERATOR_ROOT / "jarvis_brain.py"
    if not brain_script.exists():
        return

    try:
        result = subprocess.run(
            [PYTHON, str(brain_script), "--mode", "optimize", "--notify"],
            capture_output=True, text=True, timeout=120,
            cwd=str(OPERATOR_ROOT)
        )
        log.info(f"Optimization output: {result.stdout[:200]}")
    except Exception as e:
        log.error(f"Post-analysis failed: {e}")

# ─── Main Pipeline ────────────────────────────────────────────────────────────
def run_daily_pipeline(dry_run: bool = False):
    """Ejecutar el pipeline completo de un día."""
    start_time = time.time()
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    log.info(f"{'='*60}")
    log.info(f"JARVIS Daily Pipeline — {today}")
    log.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    log.info(f"{'='*60}")

    init_sched_db()
    notify(f"🚀 *JARVIS iniciando pipeline diario*\n📅 {today}\n{'🧪 DRY RUN' if dry_run else '🔴 LIVE'}")

    # Paso 1: Plan del día
    plan = get_daily_plan()
    run_id = start_run(plan)
    products = plan.get("productos_a_investigar", ["wireless earbuds"])
    n_videos = plan.get("videos_a_crear", 2)

    notify(f"📋 *Plan de hoy:*\n🎯 {plan.get('objetivo_del_dia','N/A')}\n🔍 Productos: {', '.join(products)}\n🎬 Videos: {n_videos}")

    # Paso 2: Research
    research_results = research_products(products, dry_run=dry_run)
    ok_research = sum(1 for r in research_results if r.get("status") == "success")
    update_run(run_id, products_researched=ok_research)
    log.info(f"Research complete: {ok_research}/{len(products)} successful")

    # Paso 3: Crear videos
    videos = create_content(products, n_videos, dry_run=dry_run)
    update_run(run_id, videos_created=len(videos))

    # Paso 4: Notificar
    elapsed = time.time() - start_time
    send_daily_summary(plan, research_results, videos, elapsed)
    update_run(run_id, status="completed", finished_at=datetime.now().isoformat())

    # Paso 5: Auto-análisis
    run_post_analysis(dry_run=dry_run)

    log.info(f"Pipeline complete in {elapsed:.0f}s")
    log.info(f"  Research: {ok_research}/{len(products)}")
    log.info(f"  Videos: {len(videos)}")

    return {"status": "ok", "videos": videos, "research": research_results}

# ─── CLI ─────────────────────────────────────────────────────────────────────
def main():
    import argparse
    ap = argparse.ArgumentParser(description="JARVIS Autonomous Daily Scheduler")
    ap.add_argument("--dry-run", action="store_true", help="Simular sin ejecutar")
    ap.add_argument("--status", action="store_true", help="Ver estado del último run")
    args = ap.parse_args()

    init_sched_db()

    if args.status:
        last = get_last_run()
        if not last:
            print("No runs found")
            return
        print(f"\n=== Last JARVIS Run ===")
        print(f"Date:    {last['run_date']}")
        print(f"Status:  {last['status']}")
        print(f"Started: {last['started_at']}")
        print(f"Finished:{last.get('finished_at','N/A')}")
        print(f"Research:{last['products_researched']} products")
        print(f"Videos:  {last['videos_created']} created")
        if last.get('errors'):
            print(f"Errors:  {last['errors']}")
        return

    # Run the pipeline
    result = run_daily_pipeline(dry_run=args.dry_run)
    print(f"\nPipeline result: {result['status']}")

if __name__ == "__main__":
    main()

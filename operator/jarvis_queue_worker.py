#!/usr/bin/env python3
"""
JARVIS QUEUE WORKER v1.0 — Cola de Tareas Persistente
=======================================================
Lee tasks.db y retoma tareas interrumpidas automáticamente.
Garantiza que ninguna tarea se pierda aunque el sistema se reinicie.

FUNCIONES:
  - Detecta tareas en estado 'pending' o 'running' (interrupted)
  - Las reencola y ejecuta con retry automático (max 3 intentos)
  - Circuit breaker: si un executor falla 3+ veces seguidas, lo suspende
  - Reporta progreso por Telegram
  - Se puede correr como daemon continuo o como one-shot

USO:
  python3 jarvis_queue_worker.py              # One-shot: procesar pendientes
  python3 jarvis_queue_worker.py --daemon     # Loop continuo cada 60s
  python3 jarvis_queue_worker.py --status     # Ver cola actual
"""

import json
import logging
import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

# ─── Rutas ────────────────────────────────────────────────────────────────────
OPERATOR_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator")
NUCLEO_ROOT   = Path("/Users/minimacm4/IMPERIO_NUCLEO")
DB_PATH       = OPERATOR_ROOT / "tasks.db"
LOG_DIR       = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/logs")
LOG_PATH      = LOG_DIR / "jarvis_queue.log"

LOG_DIR.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(OPERATOR_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [QUEUE] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger("jarvis_queue")

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

# ─── Circuit Breaker State ────────────────────────────────────────────────────
_circuit_breakers: dict[str, dict] = {}
MAX_FAILURES = 3
BREAKER_RESET_SECONDS = 300  # 5 minutos

def _is_breaker_tripped(executor_name: str) -> bool:
    breaker = _circuit_breakers.get(executor_name, {})
    if not breaker:
        return False
    if breaker.get("failures", 0) >= MAX_FAILURES:
        # Verificar si ya pasó el reset time
        if time.time() - breaker.get("last_failure", 0) > BREAKER_RESET_SECONDS:
            log.info(f"Circuit breaker reset for: {executor_name}")
            _circuit_breakers[executor_name] = {}
            return False
        return True
    return False

def _record_failure(executor_name: str):
    breaker = _circuit_breakers.setdefault(executor_name, {"failures": 0})
    breaker["failures"] = breaker.get("failures", 0) + 1
    breaker["last_failure"] = time.time()
    if breaker["failures"] >= MAX_FAILURES:
        log.warning(f"⚡ Circuit breaker TRIPPED for: {executor_name}")
        _notify(f"⚡ JARVIS Circuit Breaker: `{executor_name}` suspendido por {MAX_FAILURES} fallos consecutivos.")

def _record_success(executor_name: str):
    _circuit_breakers.pop(executor_name, None)

# ─── Telegram ─────────────────────────────────────────────────────────────────
def _notify(text: str) -> bool:
    if not TELEGRAM_TOKEN:
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
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        log.warning(f"Telegram failed: {e}")
        return False

# ─── Database Operations ──────────────────────────────────────────────────────
def get_pending_tasks(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """Obtener tareas pendientes o interrupted."""
    try:
        rows = conn.execute("""
            SELECT id, task_type, params, status, retry_count, created_at
            FROM tasks
            WHERE status IN ('pending', 'interrupted', 'queued')
            ORDER BY created_at ASC
            LIMIT ?
        """, (limit,)).fetchall()
    except sqlite3.OperationalError:
        # retry_count might not exist in older schema
        try:
            rows = conn.execute("""
                SELECT id, task_type, params, status, 0 as retry_count, created_at
                FROM tasks
                WHERE status IN ('pending', 'queued')
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,)).fetchall()
        except Exception as e:
            log.error(f"DB read error: {e}")
            return []

    cols = ["id", "task_type", "params", "status", "retry_count", "created_at"]
    return [dict(zip(cols, r)) for r in rows]

def update_task_status(conn: sqlite3.Connection, task_id: int, status: str,
                       result: str = None, error: str = None):
    """Actualizar estado de una tarea."""
    try:
        if result or error:
            conn.execute("""
                UPDATE tasks SET status=?, result_summary=?, updated_at=datetime('now')
                WHERE id=?
            """, (status, result or error, task_id))
        else:
            conn.execute(
                "UPDATE tasks SET status=?, updated_at=datetime('now') WHERE id=?",
                (status, task_id)
            )
        conn.commit()
    except sqlite3.OperationalError:
        # Fallback: solo status
        try:
            conn.execute("UPDATE tasks SET status=? WHERE id=?", (status, task_id))
            conn.commit()
        except Exception as e:
            log.error(f"Task update failed: {e}")

def increment_retry(conn: sqlite3.Connection, task_id: int) -> int:
    """Incrementar contador de reintentos. Retorna nuevo valor."""
    try:
        conn.execute("""
            UPDATE tasks SET retry_count = COALESCE(retry_count, 0) + 1
            WHERE id=?
        """, (task_id,))
        conn.commit()
        row = conn.execute("SELECT COALESCE(retry_count, 0) FROM tasks WHERE id=?", (task_id,)).fetchone()
        return row[0] if row else 1
    except Exception:
        return 1

def get_queue_summary(conn: sqlite3.Connection) -> dict:
    """Resumen del estado de la cola."""
    try:
        rows = conn.execute("""
            SELECT status, COUNT(*) FROM tasks GROUP BY status
        """).fetchall()
        return {r[0]: r[1] for r in rows}
    except Exception:
        return {}

# ─── Task Executor ────────────────────────────────────────────────────────────
def execute_task(task: dict) -> tuple[bool, str]:
    """
    Ejecutar una tarea individual.
    Retorna (success, message).
    """
    task_type = task.get("task_type", "")
    raw_params = task.get("params", "{}")

    # Parsear params
    if isinstance(raw_params, str):
        try:
            params = json.loads(raw_params)
        except json.JSONDecodeError:
            params = {"raw": raw_params}
    else:
        params = raw_params or {}

    log.info(f"Executing task {task['id']}: {task_type} | params={str(params)[:80]}")

    # Circuit breaker check
    if _is_breaker_tripped(task_type):
        return False, f"Circuit breaker active for {task_type} — skipping"

    try:
        # ── Research Tasks ──
        if task_type in ("research", "amazon_research"):
            from executors.research_executor import run_research
            result = run_research(params, f"queue_{task['id']}")
            if result.get("status") == "success":
                _record_success(task_type)
                return True, result.get("summary", "Research completed")
            else:
                _record_failure(task_type)
                return False, result.get("error", "Research failed")

        # ── Content Pipeline ──
        elif task_type in ("content_pipeline", "video"):
            from executors.content_pipeline_executor import run_content_pipeline
            result = run_content_pipeline(params, f"queue_{task['id']}")
            if result.get("status") == "success":
                _record_success(task_type)
                return True, f"Video: {result.get('output_path','created')}"
            else:
                _record_failure(task_type)
                return False, result.get("error", "Pipeline failed")

        # ── MediaFactory ──
        elif task_type in ("mediafactory", "pixelle_video"):
            from executors.mediafactory_executor import run_mediafactory
            result = run_mediafactory(params, f"queue_{task['id']}")
            ok = result.get("status") == "success"
            if ok:
                _record_success(task_type)
            else:
                _record_failure(task_type)
            return ok, result.get("output_path", result.get("error", ""))

        # ── Browser ──
        elif task_type in ("browser", "scrape"):
            from executors.browser_executor import run_browser
            result = run_browser(params, f"queue_{task['id']}")
            ok = result.get("status") == "success"
            if ok:
                _record_success(task_type)
            else:
                _record_failure(task_type)
            return ok, result.get("data", result.get("error", ""))[:200]

        # ── Unknown ──
        else:
            log.warning(f"Unknown task type: {task_type}")
            return False, f"Unknown task type: {task_type}"

    except ImportError as e:
        log.error(f"Import error for {task_type}: {e}")
        _record_failure(task_type)
        return False, f"Import error: {e}"
    except Exception as e:
        log.error(f"Task execution error: {e}")
        _record_failure(task_type)
        return False, str(e)

# ─── Worker Principal ─────────────────────────────────────────────────────────
def process_queue(one_shot: bool = True) -> dict:
    """Procesar la cola de tareas pendientes."""
    if not DB_PATH.exists():
        log.info("tasks.db not found — queue is empty")
        return {"processed": 0, "success": 0, "failed": 0}

    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row

    summary = get_queue_summary(conn)
    pending_count = sum(v for k, v in summary.items() if k in ("pending", "queued", "interrupted"))

    if pending_count == 0:
        log.info("Queue is empty — nothing to process")
        conn.close()
        return {"processed": 0, "success": 0, "failed": 0, "summary": summary}

    log.info(f"Queue: {summary} — processing up to 5 pending tasks")

    tasks = get_pending_tasks(conn, limit=5)
    processed = success = failed = 0

    for task in tasks:
        task_id = task["id"]
        retry = task.get("retry_count", 0)

        if retry >= MAX_FAILURES:
            log.warning(f"Task {task_id} ({task['task_type']}) exceeded max retries ({retry}) — marking dead")
            update_task_status(conn, task_id, "dead", error=f"Max retries ({MAX_FAILURES}) exceeded")
            failed += 1
            continue

        # Marcar como running
        update_task_status(conn, task_id, "running")

        # Ejecutar
        ok, message = execute_task(task)
        processed += 1

        if ok:
            update_task_status(conn, task_id, "completed", result=message[:500])
            success += 1
            log.info(f"  ✓ Task {task_id} completed: {message[:80]}")
        else:
            new_retry = increment_retry(conn, task_id)
            if new_retry >= MAX_FAILURES:
                update_task_status(conn, task_id, "dead", error=message[:500])
                log.error(f"  ✗ Task {task_id} DEAD after {new_retry} retries: {message[:80]}")
                _notify(f"💀 JARVIS: Task `{task['task_type']}` #{task_id} muerta tras {new_retry} intentos.\nError: `{message[:100]}`")
            else:
                update_task_status(conn, task_id, "pending", error=message[:500])
                log.warning(f"  ⚠ Task {task_id} failed (retry {new_retry}/{MAX_FAILURES}): {message[:80]}")

        # Pequeña pausa entre tareas
        time.sleep(2)

    conn.close()

    result = {"processed": processed, "success": success, "failed": failed - (failed - failed)}
    log.info(f"Queue pass complete: {processed} processed, {success} success, {failed} failed")

    if processed > 0:
        _notify(f"🔄 *JARVIS Queue Worker*\n✅ {success} completadas | ❌ {failed} fallidas | 📋 {processed} procesadas")

    return result

# ─── Daemon Mode ──────────────────────────────────────────────────────────────
def run_daemon(interval_seconds: int = 60):
    """Modo daemon: revisar cola cada N segundos."""
    log.info(f"JARVIS Queue Worker daemon started (interval: {interval_seconds}s)")
    _notify(f"🔄 *JARVIS Queue Worker* iniciado\nRevisando cola cada {interval_seconds}s")

    while True:
        try:
            process_queue(one_shot=False)
        except Exception as e:
            log.error(f"Queue pass failed: {e}")
        time.sleep(interval_seconds)

# ─── CLI ─────────────────────────────────────────────────────────────────────
def main():
    import argparse
    ap = argparse.ArgumentParser(description="JARVIS Queue Worker — Persistent Task Retry")
    ap.add_argument("--daemon", action="store_true", help="Run as continuous daemon")
    ap.add_argument("--interval", type=int, default=60, help="Daemon check interval (seconds)")
    ap.add_argument("--status", action="store_true", help="Show current queue status")
    args = ap.parse_args()

    if args.status:
        if not DB_PATH.exists():
            print("tasks.db not found")
            return
        conn = sqlite3.connect(DB_PATH)
        summary = get_queue_summary(conn)
        pending = get_pending_tasks(conn, limit=10)
        conn.close()
        print("\n=== JARVIS Queue Status ===")
        for status, count in summary.items():
            icon = {"completed":"✅","pending":"⏳","running":"🔄","failed":"❌","dead":"💀"}.get(status,"•")
            print(f"  {icon} {status}: {count}")
        print(f"\nNext pending tasks ({len(pending)}):")
        for t in pending[:5]:
            print(f"  #{t['id']} {t['task_type']} (retry:{t.get('retry_count',0)}) @ {t['created_at'][:16]}")
        return

    if args.daemon:
        run_daemon(interval_seconds=args.interval)
    else:
        result = process_queue()
        print(f"\nQueue result: {result}")

if __name__ == "__main__":
    main()

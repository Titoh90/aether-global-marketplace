"""
TASK MANAGER — CashClaw Economic Loop
Lifecycle: queued → running → success/failed
Every task has a real trail: logs, timestamps, result.
"""
import sqlite3
import uuid
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator/tasks.db")
log = logging.getLogger("task_manager")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if not exist."""
    conn = _get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id         TEXT PRIMARY KEY,
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL,
        source          TEXT DEFAULT 'telegram',
        pipeline        TEXT NOT NULL,
        intent          TEXT NOT NULL,
        params          TEXT DEFAULT '{}',
        status          TEXT DEFAULT 'queued',
        result          TEXT,
        error           TEXT,
        revenue_usd     REAL DEFAULT 0,
        telegram_msg_id INTEGER,
        telegram_chat_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS revenue_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        logged_at   TEXT NOT NULL,
        task_id     TEXT,
        pipeline    TEXT NOT NULL,
        description TEXT,
        amount_usd  REAL NOT NULL,
        verified    INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS paused_pipelines (
        pipeline    TEXT PRIMARY KEY,
        paused_at   TEXT,
        reason      TEXT
    );

    -- Confirmaciones pendientes (RED gate, sobrevive reinicios)
    -- TTL: 30 minutos. Después se auto-expiran.
    CREATE TABLE IF NOT EXISTS pending_confirmations (
        chat_id     INTEGER PRIMARY KEY,
        intent_json TEXT NOT NULL,
        risk_json   TEXT NOT NULL,
        created_at  TEXT NOT NULL,
        expires_at  TEXT NOT NULL
    );

    -- Traces de ejecución (para reliability scoring en arbitration)
    CREATE TABLE IF NOT EXISTS execution_traces (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id         TEXT,
        pipeline        TEXT NOT NULL,
        action          TEXT NOT NULL,
        tool_used       TEXT NOT NULL,
        tool_fallback   INTEGER DEFAULT 0,
        risk_level      TEXT,
        started_at      REAL NOT NULL,   -- unix timestamp
        ended_at        REAL,
        duration_s      REAL,
        success         INTEGER NOT NULL, -- 0 or 1
        error           TEXT,
        logged_at       TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_traces_tool ON execution_traces(tool_used);
    CREATE INDEX IF NOT EXISTS idx_traces_pipeline ON execution_traces(pipeline, action);
    """)
    conn.commit()
    conn.close()


def create_task(
    pipeline: str,
    intent: str,
    params: dict,
    source: str = "telegram",
    telegram_msg_id: Optional[int] = None,
    telegram_chat_id: Optional[int] = None,
) -> str:
    """Create task, returns task_id."""
    task_id = str(uuid.uuid4())[:8]
    now = _now()
    conn = _get_conn()
    conn.execute(
        """INSERT INTO tasks
           (task_id, created_at, updated_at, source, pipeline, intent, params,
            status, telegram_msg_id, telegram_chat_id)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (task_id, now, now, source, pipeline, intent,
         json.dumps(params), "queued", telegram_msg_id, telegram_chat_id)
    )
    conn.commit()
    conn.close()
    log.info(f"Task created: {task_id} | {pipeline} | {intent[:50]}")
    return task_id


def set_running(task_id: str):
    _update_status(task_id, "running")


def set_success(task_id: str, result: dict, revenue_usd: float = 0):
    conn = _get_conn()
    conn.execute(
        "UPDATE tasks SET status='success', result=?, revenue_usd=?, updated_at=? WHERE task_id=?",
        (json.dumps(result), revenue_usd, _now(), task_id)
    )
    conn.commit()
    conn.close()
    log.info(f"Task success: {task_id} | revenue=${revenue_usd}")


def set_failed(task_id: str, error: str):
    conn = _get_conn()
    conn.execute(
        "UPDATE tasks SET status='failed', error=?, updated_at=? WHERE task_id=?",
        (error[:500], _now(), task_id)
    )
    conn.commit()
    conn.close()
    log.warning(f"Task failed: {task_id} | {error[:100]}")


def _update_status(task_id: str, status: str):
    conn = _get_conn()
    conn.execute(
        "UPDATE tasks SET status=?, updated_at=? WHERE task_id=?",
        (status, _now(), task_id)
    )
    conn.commit()
    conn.close()


def get_task(task_id: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_pending_tasks() -> list:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE status IN ('queued','running') ORDER BY created_at"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_tasks(limit: int = 10) -> list:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT task_id, pipeline, intent, status, created_at, revenue_usd "
        "FROM tasks ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_revenue(pipeline: str, description: str, amount_usd: float,
                task_id: Optional[str] = None):
    """Log REAL revenue. Only call when money actually happens."""
    conn = _get_conn()
    conn.execute(
        "INSERT INTO revenue_log (logged_at, task_id, pipeline, description, amount_usd) "
        "VALUES (?,?,?,?,?)",
        (_now(), task_id, pipeline, description, amount_usd)
    )
    conn.commit()
    conn.close()
    log.info(f"Revenue logged: ${amount_usd} | {pipeline} | {description}")


def is_pipeline_paused(pipeline: str) -> bool:
    conn = _get_conn()
    row = conn.execute(
        "SELECT pipeline FROM paused_pipelines WHERE pipeline=?", (pipeline,)
    ).fetchone()
    conn.close()
    return row is not None


def pause_pipeline(pipeline: str, reason: str):
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO paused_pipelines (pipeline, paused_at, reason) VALUES (?,?,?)",
        (pipeline, _now(), reason)
    )
    conn.commit()
    conn.close()


def resume_pipeline(pipeline: str):
    conn = _get_conn()
    conn.execute("DELETE FROM paused_pipelines WHERE pipeline=?", (pipeline,))
    conn.commit()
    conn.close()


# ─── Pending Confirmations (persistent, survives restarts) ────────────────────

_CONFIRM_TTL_SECONDS = 1800  # 30 minutos


def store_confirmation(chat_id: int, intent: dict, risk_result_dict: dict):
    """Guarda confirmación pendiente. Reemplaza si ya hay una para ese chat_id."""
    from datetime import timedelta
    now_dt = datetime.now(timezone.utc)
    expires_dt = now_dt + timedelta(seconds=_CONFIRM_TTL_SECONDS)
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO pending_confirmations
           (chat_id, intent_json, risk_json, created_at, expires_at)
           VALUES (?, ?, ?, ?, ?)""",
        (
            chat_id,
            json.dumps(intent),
            json.dumps(risk_result_dict),
            now_dt.isoformat(),
            expires_dt.isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_confirmation(chat_id: int) -> tuple[dict, dict] | None:
    """
    Retorna (intent, risk_dict) si hay confirmación pendiente no expirada.
    Retorna None si no existe o expiró.
    Auto-limpia entradas expiradas.
    """
    now = _now()
    conn = _get_conn()

    # Limpiar expiradas
    conn.execute("DELETE FROM pending_confirmations WHERE expires_at < ?", (now,))
    conn.commit()

    row = conn.execute(
        "SELECT intent_json, risk_json FROM pending_confirmations WHERE chat_id=?",
        (chat_id,),
    ).fetchone()
    conn.close()

    if not row:
        return None
    return json.loads(row["intent_json"]), json.loads(row["risk_json"])


def clear_confirmation(chat_id: int):
    """Borra confirmación pendiente para este chat_id (después de respuesta)."""
    conn = _get_conn()
    conn.execute("DELETE FROM pending_confirmations WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()


# ─── Execution Traces (para reliability scoring en arbitration) ───────────────

def log_trace(
    task_id: str,
    pipeline: str,
    action: str,
    tool_used: str,
    success: bool,
    started_at: float,
    ended_at: float,
    risk_level: str = "",
    tool_fallback: bool = False,
    error: str = "",
):
    """Registra traza de ejecución. Alimenta el reliability scorer."""
    conn = _get_conn()
    conn.execute(
        """INSERT INTO execution_traces
           (task_id, pipeline, action, tool_used, tool_fallback, risk_level,
            started_at, ended_at, duration_s, success, error, logged_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            task_id, pipeline, action, tool_used,
            1 if tool_fallback else 0,
            risk_level,
            started_at, ended_at,
            round(ended_at - started_at, 3),
            1 if success else 0,
            error[:500] if error else "",
            _now(),
        ),
    )
    conn.commit()
    conn.close()


def get_tool_reliability(tool_name: str, min_samples: int = 5) -> float | None:
    """
    Retorna tasa de éxito histórica para una tool (0.0-1.0).
    Retorna None si hay menos de min_samples registros (no hay datos suficientes).
    """
    conn = _get_conn()
    row = conn.execute(
        """SELECT COUNT(*) as total, SUM(success) as successes
           FROM execution_traces WHERE tool_used=?""",
        (tool_name,),
    ).fetchone()
    conn.close()

    if not row or row["total"] < min_samples:
        return None
    return row["successes"] / row["total"]


def get_recent_traces(limit: int = 5) -> list[dict]:
    """Retorna los últimos N execution traces ordenados más reciente primero."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT task_id, pipeline, action, tool_used, tool_fallback,
                  risk_level, duration_s, success, error, logged_at
           FROM execution_traces
           ORDER BY rowid DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def format_task_list(tasks: list) -> str:
    if not tasks:
        return "No hay tareas recientes."
    lines = ["📋 *Tareas recientes:*"]
    icons = {"queued": "⏳", "running": "🔄", "success": "✅", "failed": "❌"}
    for t in tasks:
        icon = icons.get(t["status"], "❓")
        rev = f" ${t['revenue_usd']:.2f}" if t.get("revenue_usd", 0) > 0 else ""
        lines.append(
            f"{icon} `{t['task_id']}` {t['pipeline']} — {t['intent'][:40]}...{rev}"
        )
    return "\n".join(lines)

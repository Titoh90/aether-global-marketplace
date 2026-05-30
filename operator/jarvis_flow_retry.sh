#!/bin/bash
# jarvis_flow_retry.sh — Retry de videos de Google Flow fallidos
# Reemplaza /tmp/flow_retry_tomorrow.sh (que se borraba al reiniciar)

PYTHON="/opt/homebrew/bin/python3.14"
OPERATOR="/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator"
LOG="/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/logs/flow_retry.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"; }

log "=== Flow Retry Check ==="

# Verificar si hay tareas de Flow fallidas en tasks.db
"$PYTHON" - << PYEOF 2>> "$LOG"
import sqlite3
from pathlib import Path
db = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/operator/tasks.db")
if not db.exists():
    print("tasks.db not found")
    exit(0)
conn = sqlite3.connect(db)
rows = conn.execute("""
    SELECT id, task_type, params FROM tasks
    WHERE status IN ('failed','interrupted') AND task_type LIKE '%flow%'
    ORDER BY created_at DESC LIMIT 3
""").fetchall()
print(f"Flow tasks to retry: {len(rows)}")
for r in rows:
    print(f"  Task {r[0]}: {r[1]}")
conn.close()
PYEOF

# Correr queue worker one-shot para procesar pendientes
"$PYTHON" "$OPERATOR/jarvis_queue_worker.py" >> "$LOG" 2>&1
log "=== Flow Retry Done ==="

-- IMPERIO OPERATOR — Task Lifecycle Schema
-- Every action that enters the system gets a row here.
-- Nothing is "done" unless this table says so.

CREATE TABLE IF NOT EXISTS tasks (
    task_id     TEXT PRIMARY KEY,          -- uuid4
    created_at  TEXT NOT NULL,             -- ISO8601
    updated_at  TEXT NOT NULL,
    source      TEXT DEFAULT 'telegram',   -- telegram | cron | api
    pipeline    TEXT NOT NULL,             -- flow_director | browser | comfy | status | ...
    intent      TEXT NOT NULL,             -- raw user command
    params      TEXT DEFAULT '{}',         -- JSON params parsed from intent
    status      TEXT DEFAULT 'queued',     -- queued | running | success | failed | cancelled
    result      TEXT,                      -- JSON result on completion
    error       TEXT,                      -- error message on failure
    revenue_usd REAL DEFAULT 0,
    telegram_msg_id INTEGER,               -- to reply to the right message
    telegram_chat_id INTEGER
);

CREATE TABLE IF NOT EXISTS revenue_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    logged_at   TEXT NOT NULL,
    task_id     TEXT,
    pipeline    TEXT NOT NULL,
    description TEXT,
    amount_usd  REAL NOT NULL,
    verified    INTEGER DEFAULT 0          -- 1 = confirmed real income
);

CREATE TABLE IF NOT EXISTS system_state (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_at  TEXT
);

-- Intentionally paused pipelines (no SYS-004 spam)
CREATE TABLE IF NOT EXISTS paused_pipelines (
    pipeline    TEXT PRIMARY KEY,
    paused_at   TEXT,
    reason      TEXT
);

"""SQLite schema and initialization."""

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
    id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    from_address TEXT NOT NULL,
    from_name TEXT DEFAULT '',
    subject TEXT DEFAULT '',
    body_text TEXT DEFAULT '',
    snippet TEXT DEFAULT '',
    received_at TEXT NOT NULL,
    importance TEXT DEFAULT 'medium',
    is_read INTEGER DEFAULT 0,
    notified INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT NOT NULL REFERENCES emails(id),
    draft_text TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    telegram_message_id INTEGER,
    followup_reminded INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reply_intents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email_id TEXT NOT NULL REFERENCES emails(id),
    intent TEXT NOT NULL,
    confidence REAL DEFAULT 0.0,
    reason TEXT DEFAULT '',
    suggested_action TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_text TEXT NOT NULL,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_emails_thread ON emails(thread_id);
CREATE INDEX IF NOT EXISTS idx_emails_received ON emails(received_at);
CREATE INDEX IF NOT EXISTS idx_emails_importance ON emails(importance);
CREATE INDEX IF NOT EXISTS idx_drafts_status ON drafts(status);
CREATE INDEX IF NOT EXISTS idx_drafts_email ON drafts(email_id);
CREATE INDEX IF NOT EXISTS idx_reply_intents_email ON reply_intents(email_id);
CREATE INDEX IF NOT EXISTS idx_rules_active ON rules(active);
"""


async def init_db(db_path: str) -> aiosqlite.Connection:
    """Initialize database and create tables if needed."""
    db = await aiosqlite.connect(db_path)
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA)
    await db.commit()
    return db

"""Async CRUD operations for the email copilot database."""

from datetime import datetime

import aiosqlite


async def save_email(
    db: aiosqlite.Connection,
    email_id: str,
    thread_id: str,
    from_address: str,
    from_name: str,
    subject: str,
    body_text: str,
    snippet: str,
    received_at: str,
) -> bool:
    """Save an email. Returns True if it was new, False if it already existed."""
    try:
        await db.execute(
            """INSERT OR IGNORE INTO emails
               (id, thread_id, from_address, from_name, subject, body_text, snippet, received_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (email_id, thread_id, from_address, from_name, subject, body_text, snippet, received_at),
        )
        await db.commit()
        return db.total_changes > 0
    except Exception:
        await db.rollback()
        raise


async def update_email_importance(db: aiosqlite.Connection, email_id: str, importance: str) -> None:
    await db.execute("UPDATE emails SET importance = ? WHERE id = ?", (importance, email_id))
    await db.commit()


async def mark_notified(db: aiosqlite.Connection, email_id: str) -> None:
    await db.execute("UPDATE emails SET notified = 1 WHERE id = ?", (email_id,))
    await db.commit()


async def get_unnotified_emails(db: aiosqlite.Connection, importance: str | None = None) -> list[dict]:
    if importance:
        cursor = await db.execute(
            "SELECT * FROM emails WHERE notified = 0 AND importance = ? ORDER BY received_at DESC",
            (importance,),
        )
    else:
        cursor = await db.execute(
            "SELECT * FROM emails WHERE notified = 0 ORDER BY received_at DESC"
        )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def save_draft(
    db: aiosqlite.Connection,
    email_id: str,
    draft_text: str,
    telegram_message_id: int | None = None,
) -> int:
    """Save a draft reply. Returns the draft ID."""
    cursor = await db.execute(
        """INSERT INTO drafts (email_id, draft_text, telegram_message_id)
           VALUES (?, ?, ?)""",
        (email_id, draft_text, telegram_message_id),
    )
    await db.commit()
    return cursor.lastrowid


async def update_draft_status(db: aiosqlite.Connection, draft_id: int, status: str) -> None:
    await db.execute(
        "UPDATE drafts SET status = ?, updated_at = ? WHERE id = ?",
        (status, datetime.now().isoformat(), draft_id),
    )
    await db.commit()


async def update_draft_text(db: aiosqlite.Connection, draft_id: int, text: str) -> None:
    await db.execute(
        "UPDATE drafts SET draft_text = ?, updated_at = ? WHERE id = ?",
        (text, datetime.now().isoformat(), draft_id),
    )
    await db.commit()


async def get_pending_drafts(db: aiosqlite.Connection) -> list[dict]:
    cursor = await db.execute(
        """SELECT d.*, e.from_address, e.from_name, e.subject
           FROM drafts d JOIN emails e ON d.email_id = e.id
           WHERE d.status = 'pending'
           ORDER BY d.created_at DESC""",
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_draft_with_email(db: aiosqlite.Connection, draft_id: int) -> dict | None:
    cursor = await db.execute(
        """SELECT d.*, e.from_address, e.from_name, e.subject, e.thread_id, e.id as email_id
           FROM drafts d JOIN emails e ON d.email_id = e.id
           WHERE d.id = ?""",
        (draft_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_email(db: aiosqlite.Connection, email_id: str) -> dict | None:
    cursor = await db.execute("SELECT * FROM emails WHERE id = ?", (email_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_today_emails(db: aiosqlite.Connection) -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    cursor = await db.execute(
        "SELECT * FROM emails WHERE received_at >= ? ORDER BY received_at DESC",
        (today,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]

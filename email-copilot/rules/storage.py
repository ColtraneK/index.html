"""CRUD operations for the rules engine."""

import aiosqlite


async def get_all_rules(db: aiosqlite.Connection) -> list[dict]:
    cursor = await db.execute(
        "SELECT * FROM rules WHERE active = 1 ORDER BY created_at ASC"
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def add_rule(db: aiosqlite.Connection, rule_text: str) -> int:
    """Add a new rule. Returns the rule ID."""
    cursor = await db.execute(
        "INSERT INTO rules (rule_text) VALUES (?)",
        (rule_text,),
    )
    await db.commit()
    return cursor.lastrowid


async def delete_rule(db: aiosqlite.Connection, rule_id: int) -> bool:
    """Soft-delete a rule. Returns True if found."""
    await db.execute("UPDATE rules SET active = 0 WHERE id = ?", (rule_id,))
    await db.commit()
    return db.total_changes > 0


async def get_rule(db: aiosqlite.Connection, rule_id: int) -> dict | None:
    cursor = await db.execute("SELECT * FROM rules WHERE id = ?", (rule_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None

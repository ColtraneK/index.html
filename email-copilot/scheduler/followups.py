"""Follow-up reminder system.

Tracks sent replies and emails awaiting responses. Sends Telegram
nudges when no reply is received within a configurable window.
"""

import logging
from datetime import datetime, timedelta

from telegram import Bot

import config
from bot.formatter import _esc
from db import operations as db_ops

logger = logging.getLogger(__name__)

async def check_followups(db, bot: Bot) -> None:
    """Check for emails that need follow-up reminders.

    Called periodically by the scheduler. Finds sent drafts with no
    reply received after the follow-up window.
    """
    overdue = await db_ops.get_overdue_followups(db, hours=config.FOLLOWUP_WINDOW_HOURS)

    if not overdue:
        return

    logger.info("Found %d overdue follow-ups.", len(overdue))

    for item in overdue:
        await _send_followup_reminder(db, bot, item)


async def _send_followup_reminder(db, bot: Bot, item: dict) -> None:
    """Send a Telegram reminder for a single overdue follow-up."""
    from_name = item.get("from_name", "Unknown")
    subject = item.get("subject", "(no subject)")
    sent_at = item.get("updated_at", "")
    draft_id = item["id"]

    # Calculate how long ago we sent it
    try:
        sent_dt = datetime.fromisoformat(sent_at)
        hours_ago = int((datetime.now() - sent_dt).total_seconds() / 3600)
        time_str = f"{hours_ago}h ago"
    except (ValueError, TypeError):
        time_str = "recently"

    text = (
        f"*Follow\\-up Reminder*\n\n"
        f"You replied to {_esc(from_name)} re: {_esc(subject)}\n"
        f"Sent: {_esc(time_str)}\n"
        f"No response received yet\\.\n\n"
        f"_Consider sending a follow\\-up\\._"
    )

    try:
        from bot.keyboards import followup_keyboard
        await bot.send_message(
            chat_id=config.TELEGRAM_AUTHORIZED_USER_ID,
            text=text,
            reply_markup=followup_keyboard(draft_id, item.get("email_id", "")),
            parse_mode="MarkdownV2",
        )
        # Mark that we sent the reminder so we don't spam
        await db_ops.mark_followup_reminded(db, draft_id)
        logger.info("Sent follow-up reminder for draft #%d (to %s)", draft_id, from_name)
    except Exception as e:
        logger.error("Failed to send follow-up reminder: %s", e)

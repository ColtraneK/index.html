"""Telegram bot command and callback handlers."""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from bot.formatter import (
    format_batch_summary,
    format_draft_list,
    format_email_notification,
    format_full_email,
    format_reply_intent,
    format_rules_list,
)
from bot.keyboards import (
    confirm_send_keyboard,
    draft_action_keyboard,
    followup_keyboard,
    reply_intent_keyboard,
    settings_keyboard,
)
from db import operations as db_ops
from rules import storage as rules_storage

logger = logging.getLogger(__name__)

# Store for edit mode: {user_id: draft_id}
_edit_mode: dict[int, int] = {}


def _authorized(func):
    """Decorator to restrict bot access to authorized user only."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != config.TELEGRAM_AUTHORIZED_USER_ID:
            logger.warning("Unauthorized access attempt from user %s", user_id)
            await update.effective_message.reply_text("Unauthorized.")
            return
        return await func(update, context)
    return wrapper


@_authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Email Co-Pilot active.\n\n"
        "Commands:\n"
        "/check - Check for new emails now\n"
        "/drafts - View pending draft replies\n"
        "/summary - Today's email summary\n"
        "/rules - View active email rules\n"
        "/addrule <text> - Add a plain-English rule\n"
        "/delrule <id> - Delete a rule\n"
        "/settings - Configure preferences\n"
        "/help - Show this help"
    )


@_authorized
async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually trigger email check."""
    await update.message.reply_text("Checking for new emails...")
    # The actual check is triggered via the scheduler's poll function
    app_data = context.application.bot_data
    poll_fn = app_data.get("poll_fn")
    if poll_fn:
        await poll_fn()
    else:
        await update.message.reply_text("Poller not configured yet.")


@_authorized
async def cmd_drafts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List pending drafts."""
    db = context.application.bot_data.get("db")
    if not db:
        await update.message.reply_text("Database not ready.")
        return

    drafts = await db_ops.get_pending_drafts(db)
    text = format_draft_list(drafts)
    await update.message.reply_text(text, parse_mode="MarkdownV2")


@_authorized
async def cmd_summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get today's email summary."""
    db = context.application.bot_data.get("db")
    if not db:
        await update.message.reply_text("Database not ready.")
        return

    emails = await db_ops.get_today_emails(db)
    text = format_batch_summary(emails)
    await update.message.reply_text(text, parse_mode="MarkdownV2")


@_authorized
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show settings menu."""
    await update.message.reply_text(
        f"Current tone: *{config.REPLY_TONE}*\n\nSelect a new tone:",
        reply_markup=settings_keyboard(),
        parse_mode="MarkdownV2",
    )


@_authorized
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


@_authorized
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses."""
    query = update.callback_query
    await query.answer()

    data = query.data
    db = context.application.bot_data.get("db")
    gmail_client = context.application.bot_data.get("gmail_client")

    if not db:
        await query.edit_message_text("Database not ready.")
        return

    if data.startswith("approve:"):
        draft_id = int(data.split(":")[1])
        await query.edit_message_text(
            f"Send draft #{draft_id}?",
            reply_markup=confirm_send_keyboard(draft_id),
        )

    elif data.startswith("send:"):
        draft_id = int(data.split(":")[1])
        draft_data = await db_ops.get_draft_with_email(db, draft_id)
        if not draft_data:
            await query.edit_message_text("Draft not found.")
            return

        if gmail_client:
            success = gmail_client.send_reply(
                thread_id=draft_data["thread_id"],
                to_address=draft_data["from_address"],
                subject=draft_data["subject"],
                body=draft_data["draft_text"],
            )
            if success:
                await db_ops.update_draft_status(db, draft_id, "sent")
                await query.edit_message_text(f"Reply sent to {draft_data['from_name']}.")
            else:
                await query.edit_message_text("Failed to send. Try again later.")
        else:
            await query.edit_message_text("Gmail client not configured.")

    elif data.startswith("edit:"):
        draft_id = int(data.split(":")[1])
        _edit_mode[update.effective_user.id] = draft_id
        draft_data = await db_ops.get_draft_with_email(db, draft_id)
        if draft_data:
            await query.edit_message_text(
                f"Editing draft #{draft_id}.\n\n"
                f"Current draft:\n{draft_data['draft_text']}\n\n"
                "Send your edited version as a message:"
            )
        else:
            await query.edit_message_text("Draft not found.")

    elif data.startswith("reject:"):
        draft_id = int(data.split(":")[1])
        await db_ops.update_draft_status(db, draft_id, "rejected")
        await query.edit_message_text(f"Draft #{draft_id} rejected.")

    elif data.startswith("cancel:"):
        draft_id = int(data.split(":")[1])
        draft_data = await db_ops.get_draft_with_email(db, draft_id)
        if draft_data:
            text = format_email_notification(
                draft_data, draft_data["draft_text"], draft_id
            )
            await query.edit_message_text(
                text,
                reply_markup=draft_action_keyboard(draft_id),
                parse_mode="MarkdownV2",
            )
        else:
            await query.edit_message_text("Draft not found.")

    elif data.startswith("full:"):
        draft_id = int(data.split(":")[1])
        draft_data = await db_ops.get_draft_with_email(db, draft_id)
        if draft_data:
            email = await db_ops.get_email(db, draft_data["email_id"])
            if email:
                text = format_full_email(email)
                await query.message.reply_text(text, parse_mode="MarkdownV2")

    elif data.startswith("followup_draft:"):
        draft_id = int(data.split(":")[1])
        draft_data = await db_ops.get_draft_with_email(db, draft_id)
        if draft_data:
            # Generate a follow-up draft using the AI drafter
            openai_client = context.application.bot_data.get("openai_client")
            if openai_client:
                from ai.drafter import draft_reply
                followup_text = await draft_reply(
                    openai_client,
                    config.OPENAI_MODEL,
                    f"Follow-up: {draft_data['subject']}",
                    f"I previously replied but haven't heard back. Original subject: {draft_data['subject']}",
                    draft_data["from_name"],
                    config.USER_NAME,
                    config.REPLY_TONE,
                )
                new_draft_id = await db_ops.save_draft(db, draft_data["email_id"], followup_text)
                await query.edit_message_text(
                    f"Follow-up draft #{new_draft_id} created.",
                    reply_markup=draft_action_keyboard(new_draft_id),
                )
            else:
                await query.edit_message_text("OpenAI client not configured.")
        else:
            await query.edit_message_text("Original draft not found.")

    elif data.startswith("followup_dismiss:"):
        draft_id = int(data.split(":")[1])
        await db_ops.mark_followup_reminded(db, draft_id)
        await query.edit_message_text("Follow-up reminder dismissed.")

    elif data.startswith("followup_snooze:"):
        draft_id = int(data.split(":")[1])
        # Reset the reminded flag and push updated_at forward by 24h
        await db.execute(
            "UPDATE drafts SET followup_reminded = 0, updated_at = datetime('now') WHERE id = ?",
            (draft_id,),
        )
        await db.commit()
        await query.edit_message_text("Snoozed. Will remind again in 24h if no reply.")

    elif data.startswith("intent_reply:"):
        email_id = data.split(":")[1]
        email = await db_ops.get_email(db, email_id)
        if email:
            openai_client = context.application.bot_data.get("openai_client")
            if openai_client:
                from ai.drafter import draft_reply
                draft_text = await draft_reply(
                    openai_client,
                    config.OPENAI_MODEL,
                    email["subject"],
                    email["body_text"],
                    email["from_name"],
                    config.USER_NAME,
                    config.REPLY_TONE,
                )
                new_draft_id = await db_ops.save_draft(db, email_id, draft_text)
                await query.edit_message_text(
                    f"Draft #{new_draft_id} created.",
                    reply_markup=draft_action_keyboard(new_draft_id),
                )
            else:
                await query.edit_message_text("OpenAI client not configured.")
        else:
            await query.edit_message_text("Email not found.")

    elif data.startswith("intent_dismiss:"):
        await query.edit_message_text("Reply notification dismissed.")

    elif data.startswith("tone:"):
        tone = data.split(":")[1]
        config.REPLY_TONE = tone
        await query.edit_message_text(f"Tone updated to: {tone}")


@_authorized
async def cmd_rules(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List active rules."""
    db = context.application.bot_data.get("db")
    if not db:
        await update.message.reply_text("Database not ready.")
        return

    rules = await rules_storage.get_all_rules(db)
    text = format_rules_list(rules)
    await update.message.reply_text(text, parse_mode="MarkdownV2")


@_authorized
async def cmd_addrule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a plain-English rule. Usage: /addrule <rule text>"""
    db = context.application.bot_data.get("db")
    if not db:
        await update.message.reply_text("Database not ready.")
        return

    rule_text = " ".join(context.args) if context.args else ""
    if not rule_text:
        await update.message.reply_text(
            "Usage: /addrule <rule in plain English>\n\n"
            "Examples:\n"
            '  /addrule Emails from @acme.com are always high priority\n'
            '  /addrule Archive anything from noreply@\n'
            '  /addrule Always draft a reply to emails mentioning "showing"'
        )
        return

    rule_id = await rules_storage.add_rule(db, rule_text)
    await update.message.reply_text(f"Rule #{rule_id} added: {rule_text}")


@_authorized
async def cmd_delrule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a rule. Usage: /delrule <id>"""
    db = context.application.bot_data.get("db")
    if not db:
        await update.message.reply_text("Database not ready.")
        return

    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /delrule <rule_id>")
        return

    rule_id = int(context.args[0])
    deleted = await rules_storage.delete_rule(db, rule_id)
    if deleted:
        await update.message.reply_text(f"Rule #{rule_id} deleted.")
    else:
        await update.message.reply_text(f"Rule #{rule_id} not found.")


@_authorized
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle free-text messages (used for draft editing)."""
    user_id = update.effective_user.id
    db = context.application.bot_data.get("db")

    if user_id in _edit_mode and db:
        draft_id = _edit_mode.pop(user_id)
        new_text = update.message.text

        await db_ops.update_draft_text(db, draft_id, new_text)
        await update.message.reply_text(
            f"Draft #{draft_id} updated. Review and approve:",
            reply_markup=draft_action_keyboard(draft_id),
        )
    else:
        await update.message.reply_text(
            "Use /check to check emails, /drafts to see pending drafts, or /help for commands."
        )


def register_handlers(app: Application) -> None:
    """Register all handlers with the Telegram application."""
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("drafts", cmd_drafts))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("rules", cmd_rules))
    app.add_handler(CommandHandler("addrule", cmd_addrule))
    app.add_handler(CommandHandler("delrule", cmd_delrule))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

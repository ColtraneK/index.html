"""Periodic Gmail polling and new email processing pipeline."""

import logging

from openai import AsyncOpenAI
from telegram import Bot

import config
from ai.drafter import draft_reply
from ai.reply_classifier import classify_reply
from ai.triage import classify_importance
from bot.formatter import format_batch_summary, format_email_notification, format_reply_intent
from bot.keyboards import draft_action_keyboard, reply_intent_keyboard
from db import operations as db_ops
from gmail.client import GmailClient
from rules import match_rules
from rules import storage as rules_storage

logger = logging.getLogger(__name__)


class EmailPoller:
    """Polls Gmail for new emails and processes them through the AI pipeline."""

    def __init__(
        self,
        gmail_client: GmailClient,
        openai_client: AsyncOpenAI,
        bot: Bot,
        db,
    ):
        self.gmail = gmail_client
        self.openai = openai_client
        self.bot = bot
        self.db = db
        self._last_email_id: str | None = None

    async def poll(self) -> None:
        """Check for new emails and process them."""
        logger.info("Polling for new emails...")

        try:
            emails = self.gmail.fetch_new_emails(
                max_results=10, since_id=self._last_email_id
            )
        except Exception as e:
            logger.error("Failed to poll emails: %s", e)
            return

        if not emails:
            logger.info("No new emails found.")
            return

        logger.info("Found %d new email(s).", len(emails))

        # Update last seen ID
        if emails:
            self._last_email_id = emails[0]["id"]

        for email in emails:
            await self._process_email(email)

    async def _process_email(self, email: dict) -> None:
        """Process a single new email through rules → triage → draft → notify."""
        # Save to DB (skip if already exists)
        is_new = await db_ops.save_email(
            self.db,
            email_id=email["id"],
            thread_id=email["thread_id"],
            from_address=email["from_address"],
            from_name=email["from_name"],
            subject=email["subject"],
            body_text=email["body_text"],
            snippet=email["snippet"],
            received_at=email["received_at"],
        )

        if not is_new:
            return

        # Check if this is a reply in an existing thread (for reply classification)
        await self._check_if_reply(email)

        # Apply user-defined rules
        force_draft = False
        rule_importance = None

        rules = await rules_storage.get_all_rules(self.db)
        if rules:
            matched = await match_rules(
                self.openai,
                config.OPENAI_MODEL,
                rules,
                email["subject"],
                email["body_text"],
                email["from_address"],
                email["from_name"],
            )
            for m in matched:
                action = m.get("action")
                if action == "set_importance":
                    rule_importance = m.get("value", "medium")
                    logger.info("Rule #%s set importance to %s", m.get("rule_id"), rule_importance)
                elif action == "archive":
                    rule_importance = "low"
                    logger.info("Rule #%s archived email", m.get("rule_id"))
                elif action == "always_draft":
                    force_draft = True
                    logger.info("Rule #%s forced draft generation", m.get("rule_id"))
                elif action == "skip":
                    logger.info("Rule #%s skipped email", m.get("rule_id"))
                    return

        # Triage (use rule override if present)
        if rule_importance:
            importance = rule_importance
        else:
            triage = await classify_importance(
                self.openai,
                config.OPENAI_MODEL,
                email["subject"],
                email["body_text"],
                email["from_name"],
            )
            importance = triage["importance"]

        await db_ops.update_email_importance(self.db, email["id"], importance)

        logger.info(
            "Email from %s classified as %s%s",
            email["from_name"],
            importance,
            " (rule override)" if rule_importance else "",
        )

        if importance == "high" or force_draft:
            await self._notify_high_priority(email)
        # Medium emails are batched (handled by batch_summary)
        # Low emails are silently archived

    async def _check_if_reply(self, email: dict) -> None:
        """If this email is a reply in a thread we've sent to, classify the intent."""
        # Check if we have any sent drafts in this thread
        cursor = await self.db.execute(
            """SELECT d.*, e.subject, e.body_text as orig_body
               FROM drafts d JOIN emails e ON d.email_id = e.id
               WHERE e.thread_id = ? AND d.status = 'sent'
               ORDER BY d.updated_at DESC LIMIT 1""",
            (email["thread_id"],),
        )
        row = await cursor.fetchone()
        if not row:
            return

        sent_draft = dict(row)
        logger.info("Reply detected in thread %s from %s - classifying intent",
                     email["thread_id"], email["from_name"])

        intent_data = await classify_reply(
            self.openai,
            config.OPENAI_MODEL,
            sent_draft.get("subject", ""),
            sent_draft.get("orig_body", "")[:500],
            email["body_text"],
            email["from_name"],
        )

        # Save intent
        await db_ops.save_reply_intent(
            self.db,
            email["id"],
            intent_data["intent"],
            intent_data["confidence"],
            intent_data.get("reason", ""),
            intent_data.get("suggested_action", ""),
        )

        # Send Telegram notification with intent classification
        text = format_reply_intent(email, intent_data)
        try:
            await self.bot.send_message(
                chat_id=config.TELEGRAM_AUTHORIZED_USER_ID,
                text=text,
                reply_markup=reply_intent_keyboard(email["id"]),
                parse_mode="MarkdownV2",
            )
        except Exception as e:
            logger.error("Failed to send reply intent notification: %s", e)

    async def _notify_high_priority(self, email: dict) -> None:
        """Generate draft and send Telegram notification for high-priority email."""
        # Generate draft reply
        draft_text = await draft_reply(
            self.openai,
            config.OPENAI_MODEL,
            email["subject"],
            email["body_text"],
            email["from_name"],
            config.USER_NAME,
            config.REPLY_TONE,
        )

        # Save draft to DB
        draft_id = await db_ops.save_draft(self.db, email["id"], draft_text)

        # Send Telegram notification
        text = format_email_notification(email, draft_text, draft_id)
        try:
            msg = await self.bot.send_message(
                chat_id=config.TELEGRAM_AUTHORIZED_USER_ID,
                text=text,
                reply_markup=draft_action_keyboard(draft_id),
                parse_mode="MarkdownV2",
            )
            await db_ops.mark_notified(self.db, email["id"])
            logger.info("Sent notification for email from %s (draft #%d)", email["from_name"], draft_id)
        except Exception as e:
            logger.error("Failed to send Telegram notification: %s", e)

    async def send_batch_summary(self) -> None:
        """Send a batch summary of medium-priority unnotified emails."""
        emails = await db_ops.get_unnotified_emails(self.db, importance="medium")
        if not emails:
            return

        text = format_batch_summary(emails)
        try:
            await self.bot.send_message(
                chat_id=config.TELEGRAM_AUTHORIZED_USER_ID,
                text=text,
                parse_mode="MarkdownV2",
            )
            for email in emails:
                await db_ops.mark_notified(self.db, email["id"])
            logger.info("Sent batch summary for %d medium-priority emails.", len(emails))
        except Exception as e:
            logger.error("Failed to send batch summary: %s", e)

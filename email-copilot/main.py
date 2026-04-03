"""Email Co-Pilot - Main entry point.

Starts the Telegram bot and email polling scheduler.
"""

import asyncio
import logging
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from openai import AsyncOpenAI
from telegram.ext import ApplicationBuilder

import config
from bot.handlers import register_handlers
from db.models import init_db
from gmail.client import GmailClient
from scheduler.poller import EmailPoller

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Suppress noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("Starting Email Co-Pilot...")

    # Initialize database
    db = await init_db(str(config.DB_PATH))
    logger.info("Database initialized at %s", config.DB_PATH)

    # Initialize Gmail client
    gmail_client = GmailClient(
        client_id=config.GMAIL_CLIENT_ID,
        client_secret=config.GMAIL_CLIENT_SECRET,
        scopes=config.GMAIL_SCOPES,
        token_path=config.GMAIL_TOKEN_PATH,
        encryption_passphrase=config.GMAIL_TOKEN_ENCRYPTION_PASSPHRASE,
    )
    logger.info("Gmail client initialized.")

    # Initialize OpenAI client
    openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
    logger.info("OpenAI client initialized (model: %s).", config.OPENAI_MODEL)

    # Build Telegram application
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    register_handlers(app)

    # Initialize email poller
    poller = EmailPoller(
        gmail_client=gmail_client,
        openai_client=openai_client,
        bot=app.bot,
        db=db,
    )

    # Store references in bot_data for handlers to access
    app.bot_data["db"] = db
    app.bot_data["gmail_client"] = gmail_client
    app.bot_data["poll_fn"] = poller.poll

    # Set up scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poller.poll,
        "interval",
        seconds=config.EMAIL_POLL_INTERVAL_SECONDS,
        id="email_poll",
        name="Email Poll",
    )
    scheduler.add_job(
        poller.send_batch_summary,
        "interval",
        seconds=config.BATCH_SUMMARY_INTERVAL_SECONDS,
        id="batch_summary",
        name="Batch Summary",
    )

    logger.info(
        "Scheduler configured: poll every %ds, batch summary every %ds.",
        config.EMAIL_POLL_INTERVAL_SECONDS,
        config.BATCH_SUMMARY_INTERVAL_SECONDS,
    )

    # Start scheduler
    scheduler.start()

    # Run initial poll
    logger.info("Running initial email poll...")
    await poller.poll()

    # Start Telegram bot (this blocks until stopped)
    logger.info("Email Co-Pilot is running. Press Ctrl+C to stop.")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    try:
        # Keep running until interrupted
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down...")
    finally:
        scheduler.shutdown()
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        await db.close()
        logger.info("Email Co-Pilot stopped.")


if __name__ == "__main__":
    asyncio.run(main())

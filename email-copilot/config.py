"""Central configuration loaded from environment variables."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        print(f"ERROR: Missing required environment variable: {key}", file=sys.stderr)
        print(f"Copy .env.example to .env and fill in your values.", file=sys.stderr)
        sys.exit(1)
    return val


# Telegram
TELEGRAM_BOT_TOKEN: str = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_AUTHORIZED_USER_ID: int = int(_require("TELEGRAM_AUTHORIZED_USER_ID"))

# Gmail OAuth2
GMAIL_CLIENT_ID: str = _require("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET: str = _require("GMAIL_CLIENT_SECRET")
GMAIL_TOKEN_ENCRYPTION_PASSPHRASE: str = _require("GMAIL_TOKEN_ENCRYPTION_PASSPHRASE")
GMAIL_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
]
GMAIL_TOKEN_PATH: Path = BASE_DIR / "token.enc"

# OpenAI
OPENAI_API_KEY: str = _require("OPENAI_API_KEY")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")

# Polling
EMAIL_POLL_INTERVAL_SECONDS: int = int(os.getenv("EMAIL_POLL_INTERVAL_SECONDS", "120"))
BATCH_SUMMARY_INTERVAL_SECONDS: int = int(os.getenv("BATCH_SUMMARY_INTERVAL_SECONDS", "1800"))

# Preferences
USER_NAME: str = os.getenv("USER_NAME", "User")
USER_EMAIL: str = os.getenv("USER_EMAIL", "")
REPLY_TONE: str = os.getenv("REPLY_TONE", "professional")

# Follow-ups
FOLLOWUP_CHECK_INTERVAL_SECONDS: int = int(os.getenv("FOLLOWUP_CHECK_INTERVAL_SECONDS", "3600"))
FOLLOWUP_WINDOW_HOURS: int = int(os.getenv("FOLLOWUP_WINDOW_HOURS", "48"))

# Database
DB_PATH: Path = BASE_DIR / "copilot.db"

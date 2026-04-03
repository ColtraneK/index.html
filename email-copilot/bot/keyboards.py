"""Inline keyboard builders for Telegram bot interactions."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def draft_action_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    """Keyboard for approving, editing, or rejecting a draft reply."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Approve", callback_data=f"approve:{draft_id}"),
            InlineKeyboardButton("Edit", callback_data=f"edit:{draft_id}"),
            InlineKeyboardButton("Reject", callback_data=f"reject:{draft_id}"),
        ],
        [
            InlineKeyboardButton("Full Email", callback_data=f"full:{draft_id}"),
        ],
    ])


def confirm_send_keyboard(draft_id: int) -> InlineKeyboardMarkup:
    """Confirmation keyboard before sending."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Send Now", callback_data=f"send:{draft_id}"),
            InlineKeyboardButton("Cancel", callback_data=f"cancel:{draft_id}"),
        ],
    ])


def settings_keyboard() -> InlineKeyboardMarkup:
    """Settings menu keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Tone: Professional", callback_data="tone:professional")],
        [InlineKeyboardButton("Tone: Casual", callback_data="tone:casual")],
        [InlineKeyboardButton("Tone: Friendly", callback_data="tone:friendly")],
        [InlineKeyboardButton("Tone: Formal", callback_data="tone:formal")],
    ])

"""Format email data for Telegram display."""

from telegram.helpers import escape_markdown

MAX_BODY_PREVIEW = 500
MAX_DRAFT_PREVIEW = 800


def format_email_notification(email: dict, draft: str, draft_id: int) -> str:
    """Format an email + draft reply for Telegram notification."""
    from_display = email.get("from_name") or email.get("from_address", "Unknown")
    subject = email.get("subject", "(no subject)")
    snippet = email.get("snippet", "")[:300]

    # Truncate draft if too long
    draft_preview = draft[:MAX_DRAFT_PREVIEW]
    if len(draft) > MAX_DRAFT_PREVIEW:
        draft_preview += "..."

    return (
        f"*New Email*\n"
        f"*From:* {_esc(from_display)}\n"
        f"*Subject:* {_esc(subject)}\n\n"
        f"*Preview:*\n{_esc(snippet)}\n\n"
        f"---\n\n"
        f"*Draft Reply \\(#{draft_id}\\):*\n"
        f"{_esc(draft_preview)}"
    )


def format_full_email(email: dict) -> str:
    """Format full email body for display."""
    from_display = email.get("from_name") or email.get("from_address", "Unknown")
    subject = email.get("subject", "(no subject)")
    body = email.get("body_text", "")[:4000]

    return (
        f"*Full Email*\n"
        f"*From:* {_esc(from_display)}\n"
        f"*Subject:* {_esc(subject)}\n\n"
        f"{_esc(body)}"
    )


def format_draft_list(drafts: list[dict]) -> str:
    """Format list of pending drafts."""
    if not drafts:
        return "No pending drafts\\."

    lines = ["*Pending Drafts:*\n"]
    for d in drafts[:10]:
        subject = d.get("subject", "(no subject)")
        from_name = d.get("from_name", "Unknown")
        lines.append(
            f"\\#{d['id']} \\- Reply to {_esc(from_name)}: {_esc(subject)}"
        )
    return "\n".join(lines)


def format_batch_summary(emails: list[dict]) -> str:
    """Format a batch summary of medium-priority emails."""
    if not emails:
        return "No new emails in this batch\\."

    lines = [f"*Email Summary \\({len(emails)} emails\\):*\n"]
    for e in emails[:15]:
        from_display = e.get("from_name") or e.get("from_address", "Unknown")
        subject = e.get("subject", "(no subject)")
        importance = e.get("importance", "medium")
        icon = {"high": "!", "medium": "-", "low": "."}
        lines.append(
            f"{icon.get(importance, '-')} {_esc(from_display)}: {_esc(subject)}"
        )
    return "\n".join(lines)


def _esc(text: str) -> str:
    """Escape text for Telegram MarkdownV2."""
    return escape_markdown(str(text), version=2)

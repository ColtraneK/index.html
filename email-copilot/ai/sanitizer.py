"""Strip PII from email content before sending to LLM APIs."""

import re

# Patterns for common PII
_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_PATTERN = re.compile(
    r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
)
_SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
_IP_PATTERN = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")


def sanitize(text: str) -> str:
    """Remove PII from text before sending to AI APIs.

    Replaces emails, phone numbers, SSNs, credit cards, and IPs
    with placeholder tokens.
    """
    text = _EMAIL_PATTERN.sub("[EMAIL]", text)
    text = _PHONE_PATTERN.sub("[PHONE]", text)
    text = _SSN_PATTERN.sub("[SSN]", text)
    text = _CREDIT_CARD_PATTERN.sub("[CREDIT_CARD]", text)
    text = _IP_PATTERN.sub("[IP_ADDRESS]", text)
    return text


def sanitize_for_triage(subject: str, body: str, from_name: str) -> dict:
    """Sanitize email fields for triage classification."""
    return {
        "subject": sanitize(subject),
        "body_preview": sanitize(body[:1500]),
        "from_name": from_name,
    }


def sanitize_for_drafting(subject: str, body: str, from_name: str) -> dict:
    """Sanitize email fields for reply drafting. Keeps more context than triage."""
    return {
        "subject": sanitize(subject),
        "body": sanitize(body[:3000]),
        "from_name": from_name,
    }

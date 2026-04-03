"""Parse Gmail API message payloads into structured data."""

import base64
import re
from email.utils import parseaddr

import html2text


def parse_message(msg: dict) -> dict:
    """Parse a Gmail API message into a clean dict.

    Returns:
        dict with keys: id, thread_id, from_address, from_name, subject,
                        body_text, snippet, received_at
    """
    headers = {}
    payload = msg.get("payload", {})
    for header in payload.get("headers", []):
        name = header["name"].lower()
        if name in ("from", "subject", "date", "to"):
            headers[name] = header["value"]

    from_name, from_address = parseaddr(headers.get("from", ""))

    body_html = _extract_body(payload, "text/html")
    body_plain = _extract_body(payload, "text/plain")

    if body_html:
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = True
        converter.body_width = 0
        body_text = converter.handle(body_html)
    elif body_plain:
        body_text = body_plain
    else:
        body_text = msg.get("snippet", "")

    return {
        "id": msg["id"],
        "thread_id": msg["threadId"],
        "from_address": from_address,
        "from_name": from_name or from_address.split("@")[0],
        "subject": headers.get("subject", "(no subject)"),
        "body_text": body_text.strip(),
        "snippet": msg.get("snippet", ""),
        "received_at": headers.get("date", ""),
    }


def _extract_body(payload: dict, mime_type: str) -> str | None:
    """Recursively extract body of given mime type from message payload."""
    if payload.get("mimeType") == mime_type:
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        result = _extract_body(part, mime_type)
        if result:
            return result

    return None

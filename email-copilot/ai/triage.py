"""Classify email importance using OpenAI GPT."""

import json
import logging

from openai import AsyncOpenAI

from ai.sanitizer import sanitize_for_triage

logger = logging.getLogger(__name__)

TRIAGE_SYSTEM_PROMPT = """You are an email triage assistant. Classify the importance of incoming emails.

Respond with ONLY a JSON object with these fields:
- "importance": one of "high", "medium", "low"
- "reason": brief explanation (max 20 words)

Classification rules:
- HIGH: Direct messages from real people requiring a response, time-sensitive requests, meeting invitations, urgent matters, messages from known contacts
- MEDIUM: Newsletters you subscribed to, automated notifications from services you use, FYI emails, non-urgent updates
- LOW: Marketing emails, spam-like content, mass mailings, social media notifications, automated alerts that need no action
"""


async def classify_importance(
    client: AsyncOpenAI,
    model: str,
    subject: str,
    body: str,
    from_name: str,
) -> dict:
    """Classify email importance. Returns {"importance": "high"|"medium"|"low", "reason": "..."}."""
    sanitized = sanitize_for_triage(subject, body, from_name)

    user_msg = f"""From: {sanitized['from_name']}
Subject: {sanitized['subject']}

Body preview:
{sanitized['body_preview']}"""

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": TRIAGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=100,
        )

        content = response.choices[0].message.content.strip()
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        result = json.loads(content)
        if result.get("importance") not in ("high", "medium", "low"):
            result["importance"] = "medium"
        return result

    except Exception as e:
        logger.error("Triage classification failed: %s", e)
        return {"importance": "medium", "reason": "Classification failed, defaulting to medium"}

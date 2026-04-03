"""Generate draft email replies using OpenAI GPT."""

import logging

from openai import AsyncOpenAI

from ai.sanitizer import sanitize_for_drafting

logger = logging.getLogger(__name__)

DRAFTER_SYSTEM_PROMPT = """You are an email reply assistant. Draft a reply to the email below.

Rules:
- Match the tone specified by the user preference
- Keep replies concise and to the point
- Be polite and professional
- Do not make up facts or commitments
- If the email doesn't need a substantive reply (e.g., just a thank you), keep it very short
- Do not include a subject line - just the body
- Sign off with the user's name
- Replace [EMAIL], [PHONE], and similar placeholders with appropriate language (e.g., "I'll reach out to you" instead of "I'll email [EMAIL]")
"""


async def draft_reply(
    client: AsyncOpenAI,
    model: str,
    subject: str,
    body: str,
    from_name: str,
    user_name: str,
    tone: str = "professional",
) -> str:
    """Generate a draft reply to an email.

    Returns the draft reply text.
    """
    sanitized = sanitize_for_drafting(subject, body, from_name)

    user_msg = f"""Tone preference: {tone}
My name: {user_name}

Email to reply to:
From: {sanitized['from_name']}
Subject: {sanitized['subject']}

{sanitized['body']}

---
Draft a reply:"""

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": DRAFTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=500,
        )

        draft = response.choices[0].message.content.strip()
        return draft

    except Exception as e:
        logger.error("Draft generation failed: %s", e)
        return f"[Draft generation failed: {e}. Please compose manually.]"

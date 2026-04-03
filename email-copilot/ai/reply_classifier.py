"""Classify reply intent using OpenAI GPT.

7-category classification system inspired by ai-sdr-agent:
  interested, question, not_interested, wants_to_book,
  referral, unsubscribe, out_of_office
"""

import json
import logging

from openai import AsyncOpenAI

from ai.sanitizer import sanitize

logger = logging.getLogger(__name__)

REPLY_CATEGORIES = [
    "interested",
    "question",
    "not_interested",
    "wants_to_book",
    "referral",
    "unsubscribe",
    "out_of_office",
]

CLASSIFIER_SYSTEM_PROMPT = """You are a reply intent classifier. Analyze the reply email and classify the sender's intent.

Respond with ONLY a JSON object with these fields:
- "intent": one of "interested", "question", "not_interested", "wants_to_book", "referral", "unsubscribe", "out_of_office"
- "confidence": float between 0.0 and 1.0
- "reason": brief explanation (max 20 words)
- "suggested_action": what the user should do next (max 30 words)

Intent definitions:
- interested: Positive response, wants to continue conversation, open to next steps
- question: Asking for more information, clarification, or details before deciding
- not_interested: Declining, saying no, not a fit, passing on the opportunity
- wants_to_book: Explicitly requesting a meeting, call, showing, or appointment
- referral: Redirecting to another person ("talk to my colleague", "CC'ing my manager")
- unsubscribe: Asking to be removed from emails, "stop emailing me", marking as spam
- out_of_office: Auto-reply, vacation notice, parental leave, will be back on [date]
"""


async def classify_reply(
    client: AsyncOpenAI,
    model: str,
    original_subject: str,
    original_body_preview: str,
    reply_body: str,
    from_name: str,
) -> dict:
    """Classify the intent of a reply email.

    Returns:
        {"intent": str, "confidence": float, "reason": str, "suggested_action": str}
    """
    user_msg = f"""Original email subject: {sanitize(original_subject)}

Original email preview (first 500 chars):
{sanitize(original_body_preview[:500])}

Reply from: {from_name}
Reply body:
{sanitize(reply_body[:2000])}"""

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=150,
        )

        content = response.choices[0].message.content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        result = json.loads(content)

        if result.get("intent") not in REPLY_CATEGORIES:
            result["intent"] = "question"
        result["confidence"] = min(1.0, max(0.0, float(result.get("confidence", 0.5))))

        return result

    except Exception as e:
        logger.error("Reply classification failed: %s", e)
        return {
            "intent": "question",
            "confidence": 0.0,
            "reason": "Classification failed",
            "suggested_action": "Review the reply manually",
        }

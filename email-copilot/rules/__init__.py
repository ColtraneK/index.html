"""Plain-English rules engine for custom email handling.

Users define rules in natural language via Telegram (/rules command).
Rules are matched against incoming emails to override default triage
behavior or trigger custom actions.

Examples:
  "Emails from @acme.com are always high priority"
  "Archive anything from noreply@"
  "Forward emails about 'listing' to my assistant"
  "Always draft a reply to emails mentioning 'showing' or 'open house'"
"""

import json
import logging

from openai import AsyncOpenAI

from ai.sanitizer import sanitize

logger = logging.getLogger(__name__)

RULE_MATCHER_PROMPT = """You are an email rule matcher. Given a set of user-defined rules and an incoming email, determine which rules (if any) apply.

Each rule has an ID and a plain-English description. Evaluate the email against ALL rules.

Respond with ONLY a JSON object:
{
  "matched_rules": [
    {
      "rule_id": <int>,
      "action": "set_importance" | "archive" | "always_draft" | "skip" | "custom_tag",
      "value": <the value for the action, e.g. "high" for set_importance>,
      "reason": "<brief explanation>"
    }
  ]
}

If no rules match, return: {"matched_rules": []}

Action types:
- set_importance: Override triage to "high", "medium", or "low"
- archive: Silently archive (treat as low, no notification)
- always_draft: Always generate a draft reply regardless of importance
- skip: Skip all processing for this email
- custom_tag: Apply a custom label/tag for organization
"""


async def match_rules(
    client: AsyncOpenAI,
    model: str,
    rules: list[dict],
    email_subject: str,
    email_body: str,
    from_address: str,
    from_name: str,
) -> list[dict]:
    """Match email against user-defined rules.

    Args:
        rules: List of {"id": int, "rule_text": str} dicts
        Other args: email metadata

    Returns:
        List of matched rule actions, e.g.:
        [{"rule_id": 1, "action": "set_importance", "value": "high", "reason": "..."}]
    """
    if not rules:
        return []

    rules_text = "\n".join(f"Rule #{r['id']}: {r['rule_text']}" for r in rules)

    user_msg = f"""User-defined rules:
{rules_text}

Incoming email:
From: {from_name} <{sanitize(from_address)}>
Subject: {sanitize(email_subject)}
Body preview: {sanitize(email_body[:1000])}"""

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": RULE_MATCHER_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=300,
        )

        content = response.choices[0].message.content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        result = json.loads(content)
        return result.get("matched_rules", [])

    except Exception as e:
        logger.error("Rule matching failed: %s", e)
        return []

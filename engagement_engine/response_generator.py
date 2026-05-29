"""
response_generator.py — Generate human-sounding comment responses.

Uses LLM via OpenRouter for complex replies (questions, purchase intent).
Uses template fallback for simple intents (compliments, humor).
"""
from __future__ import annotations

import json
import os
import random
import urllib.request
from .brand_personality import get_personality, build_system_prompt
from .comment_classifier import (
    INTENT_PURCHASE, INTENT_QUESTION, INTENT_VIRAL,
    INTENT_COMPLIMENT, INTENT_HUMOR, INTENT_NEUTRAL,
)

def _get_openrouter_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        try:
            import subprocess
            key = subprocess.check_output(
                ["launchctl", "getenv", "OPENROUTER_API_KEY"],
                text=True, timeout=5
            ).strip()
        except Exception:
            pass
    return key

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_MODEL = "meta-llama/llama-3.1-8b-instruct"


def generate_response(
    comment_text: str,
    intent: str,
    category: str = "default",
    product_name: str = "",
    product_info: str = "",
) -> dict:
    """
    Generate a response for a comment.

    Returns:
        {
            "response": str,
            "method": "llm" | "template",
            "intent": str,
            "confidence": float
        }
    """
    personality = get_personality(category)

    # Template-based for simple intents (saves LLM tokens)
    if intent in (INTENT_COMPLIMENT, INTENT_HUMOR, INTENT_VIRAL, INTENT_NEUTRAL):
        response = _template_response(intent, personality, product_name)
        if response:
            return {
                "response": response,
                "method": "template",
                "intent": intent,
                "confidence": 0.85,
            }

    # LLM for complex intents (questions, purchase intent)
    if _get_openrouter_key():
        response = _llm_response(comment_text, intent, category, product_name, product_info)
        if response:
            # Enforce max length
            max_len = personality.get("max_length", 120)
            if len(response) > max_len:
                # Truncate at last complete word
                response = response[:max_len].rsplit(" ", 1)[0]
            return {
                "response": response,
                "method": "llm",
                "intent": intent,
                "confidence": 0.9,
            }

    # Final fallback: template for any intent
    response = _template_response(intent, personality, product_name)
    return {
        "response": response or "🔥",
        "method": "template_fallback",
        "intent": intent,
        "confidence": 0.6,
    }


def _template_response(intent: str, personality: dict, product_name: str = "") -> str | None:
    """Pick a random template response for the intent."""
    templates = personality.get("response_templates", {})
    options = templates.get(intent, [])

    if not options:
        # Try neutral/compliment as generic fallback
        options = templates.get("compliment", ["🔥"])

    if not options:
        return None

    template = random.choice(options)

    # Replace placeholders
    if "{product}" in template:
        template = template.replace("{product}", product_name or "this one")
    if "{answer}" in template:
        template = template.replace("{answer}", "it's legit")

    return template


def _llm_response(
    comment: str,
    intent: str,
    category: str,
    product_name: str,
    product_info: str,
) -> str | None:
    """Generate response via OpenRouter LLM."""
    system = build_system_prompt(category)

    context = f"Product: {product_name}" if product_name else ""
    if product_info:
        context += f"\nProduct details: {product_info}"

    intent_hint = {
        INTENT_PURCHASE: "This person wants to buy. Direct them to 'link in bio'. Keep it casual and urgent.",
        INTENT_QUESTION: "Answer their question directly. Be helpful but brief. One sentence max.",
    }.get(intent, "Reply naturally. Match their energy.")

    user_prompt = f"""{context}

Comment to reply to: "{comment}"

Intent: {intent_hint}

Reply (one short sentence, casual, human):"""

    try:
        payload = json.dumps({
            "model": _MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": 60,
            "temperature": 0.9,  # high temp = more human variance
        }).encode()

        req = urllib.request.Request(
            _OPENROUTER_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {_get_openrouter_key()}",
                "Content-Type": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        text = data["choices"][0]["message"]["content"].strip()

        # Clean up LLM artifacts
        text = text.strip('"\'')
        # Remove any "Response:" or "Reply:" prefix
        for prefix in ["Response:", "Reply:", "Answer:"]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()

        # Check against forbidden patterns
        personality = get_personality(category)
        for forbidden in personality.get("forbidden_patterns", []):
            if forbidden.lower() in text.lower():
                return None  # Reject, fall back to template

        return text

    except Exception:
        return None

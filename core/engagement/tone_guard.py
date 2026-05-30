#!/usr/bin/env python3
"""
tone_guard.py — Validates generated responses against engagement rules.

RULES (from plan):
  1. NEVER invent prices
  2. ALWAYS use affiliate link from post (or reference it correctly)
  3. MAX 2-3 sentences
  4. Natural human tone
  5. Soft CTA only when appropriate
  6. NO robotic language

Usage:
    from core.engagement.tone_guard import validate

    result = validate(response_text, intent, has_affiliate_link=True)
    print(result.passed_tone_check)  # True/False
    print(result.tone_issues)        # list of violated rule descriptions
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.engagement.schemas import ResponseResult

# ── Robotic phrases to reject ────────────────────────────────────────────────
# Case-insensitive. If ANY of these appear, the response fails tone check.

_ROBOTIC_PATTERNS: list[str] = [
    "certainly",
    "i would be happy",
    "i'd be happy",
    "i am happy to",
    "i'm happy to",
    "please let me know",
    "don't hesitate",
    "do not hesitate",
    "feel free to",
    "thank you for your",
    "thanks for your question",
    "thank you for reaching",
    "as an ai",
    "as a language model",
    "i hope this",
    "i hope that helps",
    "let me know if you",
    "if you have any",
    "best regards",
    "sincerely",
    "i am here to",
    "i'm here to",
    "how may i",
    "how can i",
    "it's my pleasure",
    "my pleasure",
]

# ── Price-invention patterns ─────────────────────────────────────────────────
# If response contains a currency symbol + digits, it might be inventing a price.

_PRICE_PATTERN = re.compile(r"[\$\€\£\¥]\s*\d+[\d,.]*|USD\s*\d+|US\$\s*\d+")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_price_invention(text: str, intent: str) -> str | None:
    """Check if response invents a price. Fails if it contains currency+digits."""
    if _PRICE_PATTERN.search(text):
        return "Response contains a price figure — never invent prices"
    return None


def _check_sentence_count(text: str) -> str | None:
    """Check max 2-3 sentences."""
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
    if len(sentences) > 3:
        return f"Response has {len(sentences)} sentences — max 3 allowed"
    return None


def _check_robotic_language(text: str) -> str | None:
    """Check for robotic/generic AI phrases."""
    text_lower = text.lower()
    for pattern in _ROBOTIC_PATTERNS:
        if pattern in text_lower:
            return f"Response contains robotic phrase: '{pattern}'"
    return None


def _check_affiliate_reference(text: str, has_affiliate_link: bool, intent: str) -> str | None:
    """
    If the parent post has an affiliate link and intent is purchase/price,
    the response should reference where to find the link (not the URL itself).
    """
    if not has_affiliate_link:
        return None

    if intent not in ("purchase_intent", "price_inquiry"):
        return None

    # Acceptable ways to reference a link
    link_references = [
        "link en la descripción",
        "link en nuestro perfil",
        "link en la bio",
        "link in bio",
        "link in description",
        "enlace en la descripción",
        "enlace en la bio",
        "enlace en el perfil",
        "descripción",
        "link 👆",
        "link arriba",
        "perfil",
    ]

    text_lower = text.lower()
    if not any(ref in text_lower for ref in link_references):
        return "Purchase/price intent response should reference where to find the affiliate link"
    return None


def _check_direct_url(text: str) -> str | None:
    """Response should never contain a direct URL."""
    if re.search(r"https?://", text):
        return "Response contains a direct URL — never include raw links"
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def validate(
    response_text:      str,
    intent:             str,
    has_affiliate_link: bool = False,
) -> ResponseResult:
    """
    Validate a generated response against ALL engagement tone rules.

    Args:
        response_text:      the generated response to validate
        intent:             classified intent (one of INTENT_TYPES)
        has_affiliate_link: whether parent post has a tracked affiliate link

    Returns:
        ResponseResult with passed_tone_check=True if ALL rules pass.
        tone_issues lists any violated rules.
    """
    if not response_text.strip():
        return ResponseResult(
            response_text="",
            passed_tone_check=True,
            tone_issues=(),
            needs_affiliate=False,
            was_generated=False,
        )

    issues: list[str] = []

    # Rule 1: No invented prices
    price_issue = _check_price_invention(response_text, intent)
    if price_issue:
        issues.append(price_issue)

    # Rule 3: Max 2-3 sentences
    sent_issue = _check_sentence_count(response_text)
    if sent_issue:
        issues.append(sent_issue)

    # Rule 4/6: No robotic language
    robot_issue = _check_robotic_language(response_text)
    if robot_issue:
        issues.append(robot_issue)

    # Rule 2: Affiliate link reference
    link_issue = _check_affiliate_reference(response_text, has_affiliate_link, intent)
    if link_issue:
        issues.append(link_issue)

    # No direct URLs
    url_issue = _check_direct_url(response_text)
    if url_issue:
        issues.append(url_issue)

    needs_cta = intent in ("purchase_intent", "price_inquiry") and has_affiliate_link

    return ResponseResult(
        response_text=response_text,
        passed_tone_check=len(issues) == 0,
        tone_issues=tuple(issues),
        needs_affiliate=needs_cta,
        was_generated=True,
    )


def sanitize(response_text: str) -> str:
    """
    Strip leading/trailing quotes and normalize whitespace.
    Does NOT modify content — just formatting.
    """
    text = response_text.strip().strip('"').strip("'").strip()
    # Collapse multiple spaces
    text = re.sub(r" +", " ", text)
    # Collapse multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text

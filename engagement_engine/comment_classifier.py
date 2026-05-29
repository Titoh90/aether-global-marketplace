"""
comment_classifier.py — Classify comment intent for response routing.

Fast, rule-based classification. No LLM needed — pattern matching is enough
for the 6 intent types and saves tokens for response generation.
"""
from __future__ import annotations

import re

# Intent types (ordered by priority for response)
INTENT_PURCHASE = "purchase_intent"   # wants to buy → highest priority
INTENT_QUESTION = "question"          # asking something → high priority
INTENT_VIRAL    = "viral_positive"    # high-engagement comment → pin candidate
INTENT_COMPLIMENT = "compliment"      # positive feedback → engage
INTENT_HUMOR    = "humor"             # funny → match energy
INTENT_HATE     = "hate"              # toxic → ignore
INTENT_SPAM     = "spam"              # promo/bot → ignore
INTENT_NEUTRAL  = "neutral"           # low-value → maybe skip

# Response priority (higher = more important to respond)
PRIORITY = {
    INTENT_PURCHASE: 100,
    INTENT_QUESTION: 90,
    INTENT_VIRAL: 80,
    INTENT_COMPLIMENT: 60,
    INTENT_HUMOR: 50,
    INTENT_NEUTRAL: 20,
    INTENT_HATE: 0,
    INTENT_SPAM: 0,
}

# ── Pattern sets ────────────────────────────────────────────────────────────

_PURCHASE_PATTERNS = [
    r"\bwhere\s+(can\s+i|do\s+(i|you)|to)\s+buy\b",
    r"\blink\b", r"\bbio\b", r"\burl\b",
    r"\bhow\s+(much|to\s+order|to\s+get|can\s+i\s+get)\b",
    r"\bprice\b", r"\bcost\b", r"\bshipping\b",
    r"\bi\s+(want|need|gotta\s+have)\b",
    r"\btake\s+my\s+money\b", r"\bshut\s+up\s+and\s+take\b",
    r"\badding?\s+to\s+cart\b", r"\bordered\b", r"\bjust\s+bought\b",
    r"\bwhere\s+is\s+this\s+from\b", r"\bwhere\s+did\s+you\s+get\b",
    r"\bcan\s+you\s+send\b", r"\bwhat\s+brand\b",
]

_QUESTION_PATTERNS = [
    r"\?$", r"\?[!]*$",
    r"^(is|are|do|does|can|could|would|will|how|what|which|where|when|why)\b",
    r"\banyone\s+(know|tried|use)\b",
    r"\b(works?|working)\s+(for|on|with)\b",
    r"\brecommend\b", r"\bworth\s+it\b", r"\bany\s+good\b",
    r"\bsafe\s+(for|to)\b", r"\bsuitable\b",
]

_HATE_PATTERNS = [
    r"\bscam\b", r"\bfake\b", r"\bgarbage\b", r"\btrash\b",
    r"\bwaste\s+of\s+money\b", r"\bripoff\b", r"\brip\s*off\b",
    r"\bf+u+c+k\b", r"\bsh+i+t\b", r"\bstupid\b", r"\bidiot\b",
    r"\bkill\s+yourself\b", r"\bdie\b",
    r"\bunfollow\b", r"\breported\b",
]

_SPAM_PATTERNS = [
    r"\bfollow\s+me\b", r"\bcheck\s+(my|out\s+my)\b",
    r"\bdm\s+(me|for)\b", r"\b(promo|collab)\s+in\s+(my\s+)?bio\b",
    r"@\w+\s+@\w+\s+@\w+",  # tag spam (3+ mentions)
    r"\b(crypto|nft|forex|earn\s+\$)\b",
    r"\bfree\s+(followers|likes|money)\b",
    r"(.)\\1{4,}",  # repeated chars like "lmaooooooo" (5+ repeats)
    r"\b(telegram|whatsapp)\s+(me|group|channel)\b",
]

_VIRAL_PATTERNS = [
    r"💀{2,}", r"😂{2,}", r"🔥{2,}",
    r"\b(dead|dying|screaming|crying)\b",
    r"\bi'm\s+(dead|screaming|crying)\b",
    r"\bthis\s+(is\s+)?everything\b",
    r"\bno\s+cap\b", r"\bfr\s+fr\b", r"\bong\b",
    r"\bunderrated\b", r"\bgoated\b",
]

_COMPLIMENT_PATTERNS = [
    r"\b(love|loving|loved)\s+(this|it|these)\b",
    r"\b(amazing|awesome|incredible|beautiful|gorgeous|stunning)\b",
    r"\b(great|nice|good|perfect|best)\s+(find|content|page|account|post)\b",
    r"\bkeep\s+(it\s+up|posting|going)\b",
    r"\b(fire|lit|goat|chef.s\s+kiss)\b",
    r"🔥|❤️|😍|💯|👏|🙌",
    r"\b(need|needed)\s+this\b",
]

_HUMOR_PATTERNS = [
    r"\blmao\b", r"\blmfao\b", r"\brofl\b",
    r"😂", r"💀", r"🤣",
    r"\bhaha\b", r"\blol\b",
    r"\bi\s+can't\b.*😂",
]


def classify(text: str) -> dict:
    """
    Classify comment intent.

    Returns:
        {
            "intent": str,
            "priority": int,
            "should_respond": bool,
            "pin_candidate": bool,
            "details": str
        }
    """
    if not text or not text.strip():
        return _result(INTENT_NEUTRAL, "empty")

    t = text.strip().lower()

    # Check in priority order
    if _matches(t, _SPAM_PATTERNS):
        return _result(INTENT_SPAM, "spam detected")

    if _matches(t, _HATE_PATTERNS):
        return _result(INTENT_HATE, "toxic content")

    if _matches(t, _PURCHASE_PATTERNS):
        return _result(INTENT_PURCHASE, "purchase intent")

    if _matches(t, _QUESTION_PATTERNS):
        return _result(INTENT_QUESTION, "question detected")

    if _matches(t, _VIRAL_PATTERNS):
        return _result(INTENT_VIRAL, "viral engagement")

    if _matches(t, _COMPLIMENT_PATTERNS):
        return _result(INTENT_COMPLIMENT, "positive feedback")

    if _matches(t, _HUMOR_PATTERNS):
        return _result(INTENT_HUMOR, "humor")

    # Short positive comments (under 30 chars, no negativity)
    if len(t) < 30 and not any(w in t for w in ["no", "bad", "hate", "ugly", "boring"]):
        return _result(INTENT_NEUTRAL, "short neutral")

    return _result(INTENT_NEUTRAL, "unclassified")


def _matches(text: str, patterns: list[str]) -> bool:
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _result(intent: str, details: str) -> dict:
    priority = PRIORITY.get(intent, 0)
    return {
        "intent": intent,
        "priority": priority,
        "should_respond": intent not in (INTENT_HATE, INTENT_SPAM) and priority >= 20,
        "pin_candidate": intent == INTENT_VIRAL and priority >= 80,
        "details": details,
    }

#!/usr/bin/env python3
"""
intent_classifier.py — Classifies comment intent via dispatch layer with local fallback.

Classification uses:
  1. dispatch("classification", payload) via inference_dispatch layer
  2. Local keyword-based fallback if dispatch fails

Usage:
    from core.engagement.intent_classifier import classify_intent

    intent = classify_intent(comment_event)
    print(intent.intent)       # "price_inquiry"
    print(intent.is_actionable) # True/False
"""

from __future__ import annotations

import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.engagement.schemas import CommentEvent, IntentResult, INTENT_TYPES

# ── Local keyword patterns (fallback when dispatch unavailable) ───────────────
# Each intent maps to a list of (keyword_list, weight) tuples.
# Matches are case-insensitive. First intent to reach threshold wins.

_LOCAL_PATTERNS: dict[str, list[tuple[list[str], float]]] = {
    "price_inquiry": [
        (["cuánto", "cuanto", "precio", "cuesta", "vale", "cost", "price", "how much", "💰"], 1.0),
    ],
    "purchase_intent": [
        (["comprar", "quiero", "lo quiero", "dónde comprar", "donde comprar", "link", "buy", "want it", "where to buy", "🛒"], 1.0),
    ],
    "curiosity": [
        (["qué es", "que es", "cómo funciona", "como funciona", "dime más", "cuéntame", "tell me", "what is", "how does", "🤔"], 0.7),
    ],
    "comparison_request": [
        (["vs", "versus", "comparación", "comparacion", "diferencia", "mejor que", "compare", "difference"], 0.9),
        (["cuál es mejor", "cual es mejor", "cuál recomiendas", "cual recomiendas", " vs ", " o "], 0.85),  # " o " only in isolation (requires spaces)
    ],
    "complaint": [
        (["malo", "mala", "estafa", "no funciona", "roto", "broken", "scam", "terrible", "worst", "😡", "👎"], 0.95),  # slightly higher to beat ambiguous patterns
    ],
    "spam": [
        (["sígueme", "follow me", "check my", "dm me", "🎁", "giveaway", "free followers", "suscríbete a mi"], 0.95),
    ],
    "support_request": [
        (["ayuda", "help", "problema", "problem", "no puedo", "error", "soporte", "support", "❓", "❔"], 0.8),
    ],
}

_LOCAL_THRESHOLD = 0.65  # minimum confidence to classify locally


# ── Helpers ───────────────────────────────────────────────────────────────────

def _local_classify(comment: CommentEvent) -> IntentResult:
    """
    Keyword-based intent classification. 100% LOCAL.

    Returns the highest-scoring intent above threshold, or defaults to "curiosity".

    Spam check runs first — if spam score is high, returns spam immediately.
    """
    text = comment.comment_text.lower().strip()
    scores: dict[str, float] = {}

    # Spam fast-path
    for keywords, weight in _LOCAL_PATTERNS.get("spam", []):
        if any(kw.lower() in text for kw in keywords):
            return IntentResult(
                intent="spam",
                confidence=0.95,
                reasoning="Local: spam keywords detected",
                is_actionable=False,
            )

    for intent, patterns in _LOCAL_PATTERNS.items():
        if intent == "spam":
            continue  # already handled
        for keywords, weight in patterns:
            for kw in keywords:
                if kw.lower() in text:
                    scores[intent] = max(scores.get(intent, 0.0), weight)

    if not scores:
        return IntentResult(
            intent="curiosity",
            confidence=0.4,
            reasoning="Local: no strong signals — defaulting to curiosity",
            is_actionable=True,
        )

    best_intent = max(scores, key=lambda k: scores[k])
    best_score = scores[best_intent]

    if best_score >= _LOCAL_THRESHOLD:
        return IntentResult(
            intent=best_intent,
            confidence=best_score,
            reasoning=f"Local: keyword match for '{best_intent}' at {best_score:.2f}",
            is_actionable=best_intent not in ("spam",),
        )

    return IntentResult(
        intent="curiosity",
        confidence=0.4,
        reasoning="Local: ambiguous — defaulting to curiosity",
        is_actionable=True,
    )


def _dispatch_classify(comment: CommentEvent) -> IntentResult:
    """
    Classify via inference_dispatch layer. Falls back to local on failure.
    """
    from core.inference_dispatch.dispatch import dispatch

    prompt = (
        f"Classify this social media comment intent into exactly one of: {', '.join(sorted(INTENT_TYPES))}.\n\n"
        f"Comment: \"{comment.comment_text}\"\n"
        f"Platform: {comment.platform}\n"
        f"Username: {comment.username}\n\n"
        f"Respond with ONLY the intent label (one word/phrase), nothing else."
    )

    result = dispatch(
        task_type="classification",
        payload={"prompt": prompt},
        max_tokens=32,
    )

    if result.success:
        raw = result.text.strip().lower()
        # Clean up the response — extract just the intent
        for intent in sorted(INTENT_TYPES, key=len, reverse=True):
            # Check for exact match or contained match
            clean_raw = raw.replace("_", " ").replace("-", " ").strip()
            clean_intent = intent.replace("_", " ")
            if clean_intent in clean_raw:
                is_actionable = intent not in ("spam",)
                return IntentResult(
                    intent=intent,
                    confidence=0.85,
                    reasoning=f"Dispatch: classified via {result.provider_used}/{result.model_used}",
                    is_actionable=is_actionable,
                )

        # Dispatch returned something but we couldn't extract intent
        return _local_classify(comment)

    # Dispatch failed — fall back to local
    local = _local_classify(comment)
    return IntentResult(
        intent=local.intent,
        confidence=local.confidence * 0.8,  # penalize for dispatch failure
        reasoning=f"Dispatch failed ({result.error[:80]}). Local fallback: {local.reasoning}",
        is_actionable=local.is_actionable,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def classify_intent(comment: CommentEvent) -> IntentResult:
    """
    Classify a comment's intent.

    Strategy:
      1. If comment is empty/invalid (validation failed in listener), return spam.
      2. Try dispatch layer for AI classification.
      3. Fall back to local keyword matching on any failure.

    Args:
        comment: normalized CommentEvent from comment_listener.listen()

    Returns:
        IntentResult — never raises.
    """
    if not comment.comment_text.strip():
        return IntentResult(
            intent="spam",
            confidence=1.0,
            reasoning="Empty comment — classified as spam",
            is_actionable=False,
        )

    try:
        return _dispatch_classify(comment)
    except Exception:
        return _local_classify(comment)

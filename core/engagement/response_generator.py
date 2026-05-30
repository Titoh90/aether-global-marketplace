#!/usr/bin/env python3
"""
response_generator.py — Generates human-sounding responses for social media comments.

Uses dispatch("caption_generation", ...) for generation.
Includes affiliate link from parent post when available and appropriate.

Usage:
    from core.engagement.response_generator import generate_response

    response = generate_response(comment, intent)
    print(response.response_text)
"""

from __future__ import annotations

import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.engagement.schemas import CommentEvent, IntentResult, ResponseResult

# ── Response templates (local fallback when dispatch fails) ───────────────────

_FALLBACK_TEMPLATES: dict[str, str | None] = {
    "price_inquiry":      "¡Hola! El precio exacto puede variar, pero puedes verlo en el link de la descripción 👆",
    "purchase_intent":    "¡Qué bueno que te gusta! Está disponible en el link de nuestro perfil 🔗",
    "curiosity":          "Es un producto increíble, la verdad lo recomiendo mucho 🙌",
    "comparison_request": "Depende de lo que busques, pero este tiene muy buenas reviews ⭐",
    "complaint":          "Lamento que hayas tenido esa experiencia. ¿Puedes contarme más para ayudarte?",
    "spam":               None,   # no response for spam
    "support_request":    "¡Claro! Cuéntame cuál es el problema y te ayudo 💪",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_prompt(comment: CommentEvent, intent: IntentResult) -> str:
    """Build the dispatch prompt for response generation."""
    link_info = ""
    if comment.has_affiliate_link:
        link_info = (
            "\nThe parent post has an affiliate link in the bio/description. "
            "You can reference 'el link en la descripción' or 'el link en nuestro perfil' but "
            "NEVER invent a URL. Just say where to find it (e.g., 'link en la descripción')."
        )

    return (
        f"You are responding to a social media comment on {comment.platform}.\n\n"
        f"Comment from @{comment.username}: \"{comment.comment_text}\"\n"
        f"Detected intent: {intent.intent} (confidence: {intent.confidence:.1%})\n"
        f"{link_info}\n\n"
        f"CRITICAL RULES:\n"
        f"- Respond in SPANISH (the commenter writes in Spanish)\n"
        f"- MAX 2-3 short sentences\n"
        f"- Natural, human, conversational tone — like a friend texting\n"
        f"- NEVER use robotic language like 'Certainly!' or 'I would be happy to'\n"
        f"- NEVER invent prices, specifications, or claims about the product\n"
        f"- NEVER include a direct URL or link — just say where to find it\n"
        f"- Use a CTA ONLY if intent is purchase_intent (e.g., 'link en la descripción')\n"
        f"- For complaints: be empathetic, ask how to help\n"
        f"- For spam: respond with empty string\n"
        f"- Include 1 emoji max, natural placement\n\n"
        f"Response:"
    )


def _dispatch_generate(comment: CommentEvent, intent: IntentResult) -> ResponseResult:
    """Generate response via dispatch layer. Falls back to templates on failure."""
    from core.inference_dispatch.dispatch import dispatch

    prompt = _build_prompt(comment, intent)

    result = dispatch(
        task_type="caption_generation",
        payload={"prompt": prompt},
        max_tokens=128,
    )

    if result.success and result.text.strip():
        return ResponseResult(
            response_text=result.text.strip(),
            passed_tone_check=False,  # tone_guard will validate
            tone_issues=(),
            needs_affiliate=intent.intent in ("purchase_intent", "price_inquiry"),
            was_generated=True,
        )

    # Dispatch failed — use fallback template
    template = _FALLBACK_TEMPLATES.get(intent.intent)
    if template is None:
        return ResponseResult(
            response_text="",
            passed_tone_check=True,
            tone_issues=(),
            needs_affiliate=False,
            was_generated=False,
        )

    return ResponseResult(
        response_text=template,
        passed_tone_check=False,
        tone_issues=(),
        needs_affiliate=intent.intent in ("purchase_intent", "price_inquiry"),
        was_generated=False,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def generate_response(
    comment: CommentEvent,
    intent: IntentResult,
) -> ResponseResult:
    """
    Generate a human-sounding response to a social media comment.

    Uses dispatch layer for AI generation with local template fallback.

    Args:
        comment: normalized CommentEvent
        intent:  classified IntentResult

    Returns:
        ResponseResult — never raises. response_text may be empty (spam, etc.).
    """
    # Spam → no response
    if intent.intent == "spam":
        return ResponseResult(
            response_text="",
            passed_tone_check=True,
            tone_issues=(),
            needs_affiliate=False,
            was_generated=False,
        )

    # Empty or very short comment → minimal response
    if len(comment.comment_text.strip()) < 2:
        return ResponseResult(
            response_text="",
            passed_tone_check=True,
            tone_issues=(),
            needs_affiliate=False,
            was_generated=False,
        )

    try:
        return _dispatch_generate(comment, intent)
    except Exception:
        template = _FALLBACK_TEMPLATES.get(intent.intent)
        return ResponseResult(
            response_text=template or "",
            passed_tone_check=False,
            tone_issues=(),
            needs_affiliate=intent.intent in ("purchase_intent", "price_inquiry"),
            was_generated=False,
        )

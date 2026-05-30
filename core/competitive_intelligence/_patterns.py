#!/usr/bin/env python3
"""
_patterns.py — Shared structural pattern extractors for competitive intelligence.

Extracts hook types and CTA types from caption text.
NEVER stores raw content — only classifies structural patterns.

Used by:
    public_scraper.py   → fingerprint_raw_post()
    caption_analyzer.py → analyze_caption()
"""

from __future__ import annotations


def extract_hook_type(first_lines_text: str) -> str:
    """
    Classify hook type from the first 1-2 lines of caption STRUCTURE.
    Uses heuristics — NEVER stores the actual text.

    Priority order ensures specific patterns win over generic ones.
    """
    text = first_lines_text.lower().strip()
    if not text:
        return "unknown"

    checks: list[tuple[str, list[str]]] = [
        ("question_led",     ["?", "cómo", "how", "por qué", "why", "qué"]),
        ("stat_claim",       ["%", "estudio", "study", "según", "according", "dato"]),
        ("curiosity_gap",    ["imagina", "imagine", "y si", "what if", "secreto", "secret", "piensa", "think"]),
        ("transformation",   ["antes", "before", "después", "after", "cambié", "changed", "logré", "achieved"]),
        ("pain_point",       ["cansado", "tired", "harto", "error", "problema", "problem", "duele", "frustrado"]),
        ("urgency_scarcity", ["último", "last", "solo", "only", "limitado", "limited", "corre", "hurry", "queda"]),
        ("storytelling",     ["historia", "story", "cuando", "when", "empecé", "started", "recuerdo", "remember"]),
    ]

    for hook_type, keywords in checks:
        if any(kw in text for kw in keywords):
            return hook_type

    # Short opening → hook_first
    first_line = text.split("\n")[0].strip()
    if len(first_line) < 40:
        return "hook_first"

    return "hook_first"  # default


def extract_cta_type(cta_area_text: str) -> str:
    """
    Extract CTA type from the last 1-2 lines of caption STRUCTURE.
    CTAs typically appear near the end of captions.

    Priority order ensures the most specific match wins.
    """
    text = cta_area_text.lower().strip()

    checks: list[tuple[str, list[str]]] = [
        ("link_in_bio",      ["link in bio", "link en bio", "link en la bio", "enlace en bio"]),
        ("comment_keyword",  ["comenta", "comment", "escribe", "di", "dime"]),
        ("swipe_up",         ["swipe up", "arrastra", "desliza"]),
        ("shop_now",         ["compra", "buy", "shop", "ordenar", "order", "consíguelo", "get it"]),
        ("save_for_later",   ["guarda", "save", "guárdalo", "save this"]),
        ("tag_friend",       ["etiqueta", "tag", "menciona", "mention", "comparte"]),
        ("follow_for_more",  ["sígueme", "follow", "suscríbete", "subscribe"]),
        ("soft_mention",     ["link", "enlace", "descripción", "description", "perfil", "profile"]),
    ]

    for cta_type, keywords in checks:
        if any(kw in text for kw in keywords):
            return cta_type

    return "none"

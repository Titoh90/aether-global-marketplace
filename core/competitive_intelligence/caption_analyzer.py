#!/usr/bin/env python3
"""
caption_analyzer.py — Analyzes caption structures from competitor fingerprints.

Extracts: hook types, CTA patterns, sentence structures, language features.
NEVER stores raw captions — only structural patterns.

Uses dispatch("classification") for nuanced analysis.
Local heuristic fallback for basic pattern detection.

Usage:
    from core.competitive_intelligence.caption_analyzer import analyze_caption

    patterns = analyze_caption(caption_text)
"""

from __future__ import annotations

import sys
from pathlib import Path

_IMPERIO_ROOT = Path(__file__).parent.parent.parent
if str(_IMPERIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_IMPERIO_ROOT))

from core.competitive_intelligence.schemas import HOOK_TYPES, CTA_TYPES
from core.competitive_intelligence._patterns import extract_hook_type, extract_cta_type


# ── Helpers ───────────────────────────────────────────────────────────────────

def _detect_caption_language(text: str) -> str:
    """Detect caption language: 'es', 'en', or 'mixed'."""
    text_lower = text.lower()
    es_markers = ["el", "la", "los", "las", "que", "con", "para", "por", "una", "más", "muy"]
    en_markers = ["the", "and", "for", "with", "that", "this", "your", "from", "have", "just"]

    es_count = sum(1 for m in es_markers if f" {m} " in f" {text_lower} ")
    en_count = sum(1 for m in en_markers if f" {m} " in f" {text_lower} ")

    if es_count > en_count + 2:
        return "es"
    if en_count > es_count + 2:
        return "en"
    return "mixed"


def _count_structural_features(text: str) -> dict:
    """Count structural features — NEVER stores text content."""
    words = text.split()
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]

    return {
        "word_count":         len(words),
        "sentence_count":     max(len(sentences), 1),
        "avg_words_per_sentence": len(words) / max(len(sentences), 1),
        "has_emoji":          any(ord(c) > 127 and not c.isalpha() for c in text),
        "emoji_count":        sum(1 for c in text if ord(c) > 127 and not c.isalpha()),
        "has_hashtags":       "#" in text,
        "hashtag_count":      text.count("#") if "#" in text else 0,
        "has_question":       "?" in text,
        "has_exclamation":    "!" in text,
        "has_numbers":        any(c.isdigit() for c in text),
        "line_count":         len([l for l in text.split("\n") if l.strip()]),
        "language":           _detect_caption_language(text),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_caption(caption: str) -> dict:
    """
    Analyze a single caption for structural patterns.

    Returns dict with:
        - hook_type: detected hook type
        - cta_type: detected CTA type
        - language: 'es', 'en', or 'mixed'
        - structural features (counts, flags)
        - pattern_tags: human-readable pattern descriptions

    NEVER stores the raw caption text after analysis.
    """
    lines = [l.strip() for l in caption.strip().split("\n") if l.strip()]
    first2 = " ".join(lines[:2])
    last2 = " ".join(lines[-2:]) if len(lines) > 1 else caption
    hook = extract_hook_type(first2)
    cta = extract_cta_type(last2)
    features = _count_structural_features(caption)

    # Build human-readable pattern descriptions
    pattern_tags: list[str] = []

    if hook == "hook_first":
        pattern_tags.append("hook-first caption")
    elif hook == "question_led":
        pattern_tags.append("question-led opening")
    elif hook == "storytelling":
        pattern_tags.append("story-driven hook")
    elif hook == "curiosity_gap":
        pattern_tags.append("curiosity gap opening")
    elif hook == "stat_claim":
        pattern_tags.append("statistic-based hook")
    elif hook == "pain_point":
        pattern_tags.append("pain-point opening")
    elif hook == "urgency_scarcity":
        pattern_tags.append("urgency/scarcity framing")

    if features["has_emoji"]:
        pattern_tags.append(f"emoji usage ({features['emoji_count']}x)")
    if features["has_hashtags"]:
        pattern_tags.append(f"hashtag strategy ({features['hashtag_count']}x)")
    if features["has_question"]:
        pattern_tags.append("engagement question")

    if cta == "soft_mention":
        pattern_tags.append("soft link mention")
    elif cta == "comment_keyword":
        pattern_tags.append("comment-to-get CTA")
    elif cta == "link_in_bio":
        pattern_tags.append("bio link CTA")

    if features["avg_words_per_sentence"] < 8:
        pattern_tags.append("short punchy sentences")
    elif features["avg_words_per_sentence"] > 20:
        pattern_tags.append("long-form caption style")

    return {
        "hook_type":   hook,
        "cta_type":    cta,
        "language":    features["language"],
        "features":    features,
        "pattern_tags": pattern_tags,
    }


def analyze_batch(captions: list[str]) -> list[dict]:
    """Analyze a batch of captions."""
    return [analyze_caption(c) for c in captions]


def summarize_patterns(analyses: list[dict]) -> dict:
    """
    Summarize patterns across multiple caption analyses.
    Returns distribution counts for hooks, CTAs, and common patterns.
    """
    hook_counts: dict[str, int] = {}
    cta_counts: dict[str, int] = {}
    all_tags: list[str] = []

    for a in analyses:
        hook = a["hook_type"]
        cta = a["cta_type"]
        hook_counts[hook] = hook_counts.get(hook, 0) + 1
        cta_counts[cta] = cta_counts.get(cta, 0) + 1
        all_tags.extend(a["pattern_tags"])

    total = max(len(analyses), 1)
    hook_dist = {k: round(v / total, 3) for k, v in hook_counts.items()}
    cta_dist = {k: round(v / total, 3) for k, v in cta_counts.items()}

    # Top 5 pattern tags
    tag_counts: dict[str, int] = {}
    for t in all_tags:
        tag_counts[t] = tag_counts.get(t, 0) + 1
    top_patterns = sorted(tag_counts, key=lambda k: tag_counts[k], reverse=True)[:5]

    dominant_hook = max(hook_counts, key=lambda k: hook_counts[k]) if hook_counts else "unknown"
    dominant_cta = max(cta_counts, key=lambda k: cta_counts[k]) if cta_counts else "none"

    return {
        "dominant_hook":     dominant_hook,
        "hook_distribution": hook_dist,
        "dominant_cta":      dominant_cta,
        "cta_distribution":  cta_dist,
        "top_patterns":      top_patterns,
    }

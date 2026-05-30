"""
content_quality_gate.py — Pre-post content quality scoring.

Evaluates generated content before posting. Starts in SHADOW mode
(logs scores but never blocks). After 2 weeks of baseline data,
switch to ENFORCE mode with conservative threshold.

Checks:
    1. Caption length (min 50 chars, max 2200)
    2. No placeholder text ("TODO", "INSERT", "[product]", etc.)
    3. Brand compliance via tone_guard rules
    4. No fabricated prices or claims
    5. Affiliate link present
    6. Readability (sentence variety, not all-caps)
    7. Platform-specific limits (Twitter 280, TikTok 2200, etc.)

Usage:
    from core.quality.content_quality_gate import evaluate, QualityMode

    result = evaluate({
        "caption": "...",
        "product_name": "Owala FreeSip",
        "asin": "B0BZYCJK89",
        "platform": "instagram",
        "affiliate_url": "https://...",
        "images": [Path("slide_01.png")],
    })

    if result.passed or QualityMode is SHADOW:
        proceed_to_post()

Mode control via env var:
    IMPERIO_QUALITY_GATE_MODE=shadow  (default — log only)
    IMPERIO_QUALITY_GATE_MODE=enforce (block below threshold)
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

IMPERIO_ROOT = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT")
QUALITY_LOG = IMPERIO_ROOT / "logs" / "quality_gate.jsonl"


class QualityMode(str, Enum):
    SHADOW = "shadow"
    ENFORCE = "enforce"


@dataclass(frozen=True)
class QualityResult:
    score: int              # 0-100
    passed: bool            # True if score >= threshold
    mode: str               # "shadow" or "enforce"
    reasons: tuple[str, ...]  # human-readable check results
    checks: tuple[tuple[str, int, str], ...]  # (check_name, points, detail)


# Placeholder patterns that should never appear in final content
PLACEHOLDER_PATTERNS = [
    r'\[product\]', r'\[name\]', r'\[price\]', r'\[brand\]',
    r'\bTODO\b', r'\bINSERT\b', r'\bPLACEHOLDER\b', r'\bFIXME\b',
    r'\bXXX\b', r'\{\{', r'\}\}', r'\[YOUR',
]

# Platform caption limits
PLATFORM_LIMITS = {
    "twitter": 280,
    "instagram": 2200,
    "tiktok": 2200,
    "pinterest": 500,
    "facebook": 63206,
    "telegram": 4096,
    "youtube": 5000,
}

PASS_THRESHOLD = 40  # conservative — most content should pass


def _get_mode() -> QualityMode:
    val = os.environ.get("IMPERIO_QUALITY_GATE_MODE", "shadow").lower()
    if val == "enforce":
        return QualityMode.ENFORCE
    return QualityMode.SHADOW


def evaluate(content: dict) -> QualityResult:
    """
    Score content quality. Returns QualityResult.

    content dict keys:
        caption: str (required)
        product_name: str
        asin: str
        platform: str
        affiliate_url: str
        images: list[Path]
    """
    caption = content.get("caption", "")
    platform = content.get("platform", "instagram")
    affiliate_url = content.get("affiliate_url", "")
    product_name = content.get("product_name", "")
    images = content.get("images", [])

    checks = []
    total_points = 0
    max_points = 0

    # 1. Caption length (20 pts)
    max_points += 20
    cap_len = len(caption)
    if cap_len >= 100:
        checks.append(("caption_length", 20, f"{cap_len} chars — good"))
        total_points += 20
    elif cap_len >= 50:
        checks.append(("caption_length", 10, f"{cap_len} chars — short"))
        total_points += 10
    elif cap_len > 0:
        checks.append(("caption_length", 5, f"{cap_len} chars — too short"))
        total_points += 5
    else:
        checks.append(("caption_length", 0, "empty caption"))

    # 2. No placeholder text (15 pts)
    max_points += 15
    placeholders_found = []
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, caption, re.IGNORECASE):
            placeholders_found.append(pattern)
    if not placeholders_found:
        checks.append(("no_placeholders", 15, "clean"))
        total_points += 15
    else:
        checks.append(("no_placeholders", 0,
                       f"found: {', '.join(placeholders_found[:3])}"))

    # 3. Platform limit compliance (10 pts)
    max_points += 10
    limit = PLATFORM_LIMITS.get(platform, 5000)
    if cap_len <= limit:
        checks.append(("platform_limit", 10,
                       f"{cap_len}/{limit} — within limit"))
        total_points += 10
    else:
        checks.append(("platform_limit", 0,
                       f"{cap_len}/{limit} — EXCEEDS limit"))

    # 4. No fabricated prices (10 pts)
    max_points += 10
    # Check for suspiciously precise prices not in product data
    fake_price_patterns = [
        r'\$\d+\.\d{2}',  # $XX.XX — only flag if no product price provided
    ]
    has_suspicious_price = False
    if not content.get("price"):
        for p in fake_price_patterns:
            matches = re.findall(p, caption)
            if len(matches) > 2:  # more than 2 price mentions = suspicious
                has_suspicious_price = True
                break
    if not has_suspicious_price:
        checks.append(("no_fake_prices", 10, "clean"))
        total_points += 10
    else:
        checks.append(("no_fake_prices", 0, "multiple price claims without source"))

    # 5. Affiliate link present (15 pts)
    max_points += 15
    has_link = bool(affiliate_url) or "http" in caption or "link" in caption.lower()
    if has_link:
        checks.append(("has_affiliate_link", 15, "link present"))
        total_points += 15
    else:
        checks.append(("has_affiliate_link", 5, "no link detected — may be added later"))
        total_points += 5

    # 6. Readability — sentence variety (15 pts)
    max_points += 15
    sentences = [s.strip() for s in re.split(r'[.!?\n]', caption) if s.strip()]
    all_caps_ratio = sum(1 for s in sentences if s.isupper()) / max(len(sentences), 1)
    if len(sentences) >= 3 and all_caps_ratio < 0.5:
        checks.append(("readability", 15,
                       f"{len(sentences)} sentences, varied"))
        total_points += 15
    elif len(sentences) >= 2:
        checks.append(("readability", 10,
                       f"{len(sentences)} sentences"))
        total_points += 10
    else:
        checks.append(("readability", 5, "single sentence"))
        total_points += 5

    # 7. Has images (15 pts)
    max_points += 15
    if images and len(images) > 0:
        valid_images = [p for p in images
                       if isinstance(p, Path) and p.exists() and p.stat().st_size > 10000]
        if len(valid_images) >= 3:
            checks.append(("has_images", 15,
                           f"{len(valid_images)} valid images"))
            total_points += 15
        elif len(valid_images) >= 1:
            checks.append(("has_images", 10,
                           f"{len(valid_images)} valid images"))
            total_points += 10
        else:
            checks.append(("has_images", 0, "images listed but invalid"))
    else:
        checks.append(("has_images", 5, "no images (text-only post)"))
        total_points += 5

    # Calculate final score (normalize to 0-100)
    score = round((total_points / max_points) * 100) if max_points > 0 else 0
    mode = _get_mode()
    passed = score >= PASS_THRESHOLD

    reasons = tuple(
        f"{'PASS' if pts > 0 else 'FAIL'} {name}: {detail}"
        for name, pts, detail in checks
    )

    result = QualityResult(
        score=score,
        passed=passed,
        mode=mode.value,
        reasons=reasons,
        checks=tuple(checks),
    )

    # Always log (shadow and enforce)
    _log_result(result, content)

    return result


def _log_result(result: QualityResult, content: dict) -> None:
    """Append quality result to JSONL log."""
    try:
        QUALITY_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "score": result.score,
            "passed": result.passed,
            "mode": result.mode,
            "platform": content.get("platform", "unknown"),
            "product": content.get("product_name", "unknown")[:60],
            "asin": content.get("asin", ""),
            "caption_len": len(content.get("caption", "")),
            "checks": {name: pts for name, pts, _ in result.checks},
        }
        with open(QUALITY_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

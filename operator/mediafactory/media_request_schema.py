from __future__ import annotations

from dataclasses import dataclass


PLATFORM_ALIASES = {
    "ig": "instagram",
    "instagram": "instagram",
    "reels": "instagram",
    "fb": "facebook",
    "facebook": "facebook",
    "tik tok": "tiktok",
    "tiktok": "tiktok",
    "youtube": "youtube",
    "youtube shorts": "youtube",
    "shorts": "youtube",
}

FORMAT_ALIASES = {
    "reel": "short",
    "reels": "short",
    "short": "short",
    "shorts": "short",
    "video": "short",
}


@dataclass(frozen=True)
class MediaRequest:
    intent: str
    topic: str
    platform: str = "tiktok"
    format: str = "short"
    goal: str = "awareness"
    budget_mode: str = "free"


def normalize_media_request(raw: dict) -> MediaRequest:
    intent = _normalize_required(raw.get("intent"), "intent")
    topic = _normalize_required(raw.get("topic"), "topic")
    platform = _normalize_platform(raw.get("platform", "tiktok"))
    media_format = _normalize_format(raw.get("format", "short"))
    goal = _normalize_optional(raw.get("goal", "awareness"), "awareness")
    budget_mode = _normalize_optional(raw.get("budget_mode", "free"), "free")
    return MediaRequest(
        intent=intent,
        topic=topic,
        platform=platform,
        format=media_format,
        goal=goal,
        budget_mode=budget_mode,
    )


def _normalize_required(value: object, field_name: str) -> str:
    normalized = _normalize_optional(value, "")
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


def _normalize_optional(value: object, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _normalize_platform(value: object) -> str:
    normalized = str(value).strip().lower()
    return PLATFORM_ALIASES.get(normalized, normalized or "tiktok")


def _normalize_format(value: object) -> str:
    normalized = str(value).strip().lower()
    return FORMAT_ALIASES.get(normalized, normalized or "short")

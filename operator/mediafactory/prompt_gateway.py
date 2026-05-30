from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


OptimizerRunner = Callable[[str], dict]


@dataclass(frozen=True)
class PromptGatewayResult:
    raw_input: str
    optimized_prompt: str
    platform: str
    format: str
    goal: str
    source: str


def optimize_user_request(
    raw_input: str, optimizer_runner: OptimizerRunner | None = None
) -> PromptGatewayResult:
    normalized_input = raw_input.strip()
    fallback = _build_fallback_result(normalized_input)

    if optimizer_runner is None:
        return fallback

    try:
        payload = optimizer_runner(normalized_input) or {}
    except Exception:
        return fallback

    optimized_prompt = str(payload.get("optimized_prompt", "")).strip()
    if not optimized_prompt:
        return fallback

    return PromptGatewayResult(
        raw_input=normalized_input,
        optimized_prompt=optimized_prompt,
        platform=_detect_platform(str(payload.get("platform", fallback.platform))),
        format=_detect_format(str(payload.get("format", fallback.format))),
        goal=_detect_goal(str(payload.get("goal", fallback.goal))),
        source="prompt_optimizer",
    )


def _build_fallback_result(raw_input: str) -> PromptGatewayResult:
    platform = _detect_platform(raw_input)
    media_format = _detect_format(raw_input)
    goal = _detect_goal(raw_input)
    topic = _infer_topic(raw_input)
    optimized_prompt = (
        f"Create a {media_format} {goal} video for {platform} about {topic}. "
        "Focus on a fast hook, clear benefit, practical use case, and a concise CTA."
    )
    return PromptGatewayResult(
        raw_input=raw_input,
        optimized_prompt=optimized_prompt,
        platform=platform,
        format=media_format,
        goal=goal,
        source="fallback",
    )


def _detect_platform(text: str) -> str:
    lowered = text.lower()
    if "reels" in lowered or "instagram" in lowered:
        return "instagram"
    if "youtube" in lowered:
        return "youtube"
    if "facebook" in lowered:
        return "facebook"
    return "tiktok"


def _detect_format(text: str) -> str:
    lowered = text.lower()
    if "story" in lowered:
        return "story"
    return "short"


def _detect_goal(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("convierte", "conversion", "vende", "sale")):
        return "conversion"
    return "awareness"


def _infer_topic(text: str) -> str:
    lowered = text.lower()
    if "herramienta" in lowered and "ia" in lowered and "ahorra tiempo" in lowered:
        return "AI tool that saves time"
    if "amazon" in lowered and "oficina" in lowered:
        return "office product"
    if "automatización" in lowered:
        return "automation for small businesses"
    return text.strip()

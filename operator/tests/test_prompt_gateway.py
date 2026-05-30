from __future__ import annotations

from mediafactory.prompt_gateway import PromptGatewayResult, optimize_user_request


def test_optimize_user_request_builds_structured_fallback_brief() -> None:
    result = optimize_user_request(
        "hazme algo para tiktok de una herramienta de ia que ahorra tiempo"
    )

    assert result == PromptGatewayResult(
        raw_input="hazme algo para tiktok de una herramienta de ia que ahorra tiempo",
        optimized_prompt=(
            "Create a short awareness video for tiktok about AI tool that saves time. "
            "Focus on a fast hook, clear benefit, practical use case, and a concise CTA."
        ),
        platform="tiktok",
        format="short",
        goal="awareness",
        source="fallback",
    )


def test_optimize_user_request_uses_optimizer_runner_when_available() -> None:
    def fake_runner(_: str) -> dict:
        return {
            "optimized_prompt": "Custom optimized prompt",
            "platform": "instagram",
            "format": "short",
            "goal": "conversion",
        }

    result = optimize_user_request(
        "quiero algo para reels sobre automatización",
        optimizer_runner=fake_runner,
    )

    assert result == PromptGatewayResult(
        raw_input="quiero algo para reels sobre automatización",
        optimized_prompt="Custom optimized prompt",
        platform="instagram",
        format="short",
        goal="conversion",
        source="prompt_optimizer",
    )


def test_optimize_user_request_keeps_traceability_when_runner_fails() -> None:
    def broken_runner(_: str) -> dict:
        raise RuntimeError("optimizer down")

    result = optimize_user_request(
        "quiero un short de amazon sobre un producto útil para oficina",
        optimizer_runner=broken_runner,
    )

    assert result.raw_input == "quiero un short de amazon sobre un producto útil para oficina"
    assert result.source == "fallback"
    assert result.platform == "tiktok"
    assert result.format == "short"
    assert "office product" in result.optimized_prompt.lower()

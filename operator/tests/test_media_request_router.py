from __future__ import annotations

from mediafactory.media_request_router import DispatchPlan, plan_media_request
from mediafactory.media_request_schema import MediaRequest
from mediafactory.model_router import ModelSelection
import hermes_core


def test_plan_media_request_selects_pixelle_worker_with_free_backend() -> None:
    result = plan_media_request(
        "hazme algo para tiktok de una herramienta de ia que ahorra tiempo",
        optimizer_runner=None,  # use static fallback — no network call in unit tests
    )

    assert result == DispatchPlan(
        pipeline="mediafactory",
        action="create_video",
        dispatcher="openclaw",
        worker="pixelle_video",
        request=MediaRequest(
            intent="create_video",
            topic="hazme algo para tiktok de una herramienta de ia que ahorra tiempo",
            platform="tiktok",
            format="short",
            goal="awareness",
            budget_mode="free",
        ),
        optimized_prompt=(
            "Create a short awareness video for tiktok about AI tool that saves time. "
            "Focus on a fast hook, clear benefit, practical use case, and a concise CTA."
        ),
        model_selection=ModelSelection(
            backend="openrouter",
            model="openrouter/free",
            reason="Free general-purpose prompt refinement and ideation.",
        ),
        prompt_source="fallback",
    )


def test_hermes_classify_routes_video_requests_to_mediafactory_slice() -> None:
    # hermes_core.classify calls plan_media_request internally — patch to avoid network
    import mediafactory.media_request_router as _router
    original = _router.plan_media_request
    try:
        _router.plan_media_request = lambda raw, **kw: original(raw, optimizer_runner=None)
        result = hermes_core.classify(
            "hazme algo para tiktok de una herramienta de ia que ahorra tiempo"
        )
    finally:
        _router.plan_media_request = original

    assert result["pipeline"] == "mediafactory"
    assert result["action"] == "create_video"
    assert result["confidence"] == "pattern"
    assert result["params"]["dispatcher"] == "openclaw"
    assert result["params"]["worker"] == "pixelle_video"
    assert result["params"]["model_backend"] == "openrouter"
    assert result["params"]["model"] == "openrouter/free"
    assert result["params"]["optimized_prompt"].startswith(
        "Create a short awareness video for tiktok"
    )

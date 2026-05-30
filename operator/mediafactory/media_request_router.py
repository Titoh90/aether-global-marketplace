from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mediafactory.media_request_schema import MediaRequest, normalize_media_request
from mediafactory.model_router import ModelSelection, choose_model_backend
from mediafactory.prompt_gateway import OptimizerRunner, optimize_user_request
from mediafactory.prompt_optimizer_runner import run_optimizer


@dataclass(frozen=True)
class DispatchPlan:
    pipeline: str
    action: str
    dispatcher: str
    worker: str
    request: MediaRequest
    optimized_prompt: str
    model_selection: ModelSelection
    prompt_source: str

    def as_params(self) -> dict[str, str]:
        return {
            "intent": self.request.intent,
            "topic": self.request.topic,
            "platform": self.request.platform,
            "format": self.request.format,
            "goal": self.request.goal,
            "budget_mode": self.request.budget_mode,
            "dispatcher": self.dispatcher,
            "worker": self.worker,
            "optimized_prompt": self.optimized_prompt,
            "prompt_source": self.prompt_source,
            "model_backend": self.model_selection.backend,
            "model": self.model_selection.model,
            "model_reason": self.model_selection.reason,
        }


def plan_media_request(
    raw_input: str, optimizer_runner: OptimizerRunner | None = run_optimizer
) -> DispatchPlan:
    prompt_result = optimize_user_request(raw_input, optimizer_runner=optimizer_runner)
    request = normalize_media_request(
        {
            "intent": "create_video",
            "topic": prompt_result.raw_input,
            "platform": prompt_result.platform,
            "format": prompt_result.format,
            "goal": prompt_result.goal,
            "budget_mode": "free",
        }
    )
    model_selection = choose_model_backend("prompt_refine")
    return DispatchPlan(
        pipeline="mediafactory",
        action="create_video",
        dispatcher="openclaw",
        worker="pixelle_video",
        request=request,
        optimized_prompt=prompt_result.optimized_prompt,
        model_selection=model_selection,
        prompt_source=prompt_result.source,
    )

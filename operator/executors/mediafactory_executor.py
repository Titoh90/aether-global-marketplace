"""
mediafactory_executor.py — Executor para el pipeline MediaFactory

Llamado desde imperio_operator_gateway.py cuando pipeline == "mediafactory".

Flujo:
  1. plan_media_request()  — optimiza prompt, elige backend
  2. run_pixelle_worker()  — genera video MP4
  3. (opcional) social_poster — postea a TikTok/Instagram

Retorna: {"status": "success"|"failed", "output_path": "...", "error": "..."}
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

OPERATOR_ROOT = Path(__file__).resolve().parents[1]
REVENUE_ROOT  = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/REVENUE")
VIDEO_OUTPUT  = REVENUE_ROOT / "videos"

if str(OPERATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(OPERATOR_ROOT))

log = logging.getLogger("mediafactory_executor")


def generate_and_post(params: dict, task_id: str) -> dict:
    """
    Genera video del producto indicado en params["topic"].
    Si params["post"] == True, postea a TikTok e Instagram.

    params keys (todos opcionales excepto topic):
      topic     — descripción del producto/video
      post      — True/False (default False)
      platform  — "tiktok"|"instagram"|"both" (default "both")
    """
    from mediafactory.media_request_router import plan_media_request
    from mediafactory.pixelle_worker import run_pixelle_worker

    topic = params.get("topic") or params.get("optimized_prompt") or params.get("intent", "")
    if not topic:
        return {"status": "failed", "error": "No topic provided in params"}

    should_post = str(params.get("post", "false")).lower() in ("true", "1", "yes", "si", "sí")
    post_platform = params.get("platform", "both")

    # Optional enriched script brief from research pipeline
    script_brief_override = params.get("script_brief")

    log.info(f"[{task_id}] MediaFactory: '{topic[:60]}' | post={should_post} | enriched={bool(script_brief_override)}")

    # ── 1. Plan ────────────────────────────────────────────────────────────────
    try:
        plan = plan_media_request(topic)
        log.info(f"[{task_id}] Plan: {plan.worker} via {plan.model_selection.backend} | source={plan.prompt_source}")
    except Exception as e:
        return {"status": "failed", "error": f"Planning failed: {e}"}

    # Apply enriched brief from research if available (overrides optimizer output)
    if script_brief_override:
        import dataclasses
        plan = dataclasses.replace(plan, optimized_prompt=script_brief_override)
        log.info(f"[{task_id}] script_brief injected from research ({len(script_brief_override)} chars)")

    # ── 2. Generate video ──────────────────────────────────────────────────────
    VIDEO_OUTPUT.mkdir(parents=True, exist_ok=True)
    try:
        result = run_pixelle_worker(plan, output_dir=VIDEO_OUTPUT)
    except Exception as e:
        return {"status": "failed", "error": f"Pixelle worker crashed: {e}"}

    if result.status != "success":
        return {
            "status": "failed",
            "error": result.error or "Pixelle returned failed status",
            "output_path": result.output_path,
        }

    log.info(f"[{task_id}] Video generated: {result.output_path}")

    # ── 3. Optionally post ─────────────────────────────────────────────────────
    post_results: list[dict] = []
    if should_post:
        post_results = _post_video(
            video_path=result.output_path,
            caption=plan.optimized_prompt,
            platform=post_platform,
            task_id=task_id,
        )

    return {
        "status": "success",
        "output_path": result.output_path,
        "metadata_path": result.metadata_path,
        "optimized_prompt": result.optimized_prompt,
        "prompt_source": plan.prompt_source,
        "backend": result.backend_used,
        "post_results": post_results,
    }


def _post_video(video_path: str, caption: str, platform: str, task_id: str) -> list[dict]:
    """Post video to social platforms. Returns list of post results."""
    import asyncio
    import importlib.util

    social_poster_path = REVENUE_ROOT / "social_poster.py"
    if not social_poster_path.exists():
        log.warning(f"[{task_id}] social_poster.py not found — skipping post")
        return [{"platform": platform, "status": "skipped", "error": "social_poster.py not found"}]

    # Dynamic import to avoid circular deps
    spec = importlib.util.spec_from_file_location("social_poster", social_poster_path)
    poster = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(poster)

    results = []
    platforms = ["tiktok", "instagram"] if platform == "both" else [platform]

    for p in platforms:
        try:
            if p == "tiktok":
                result = asyncio.run(poster.post_to_tiktok(video_path, caption))
            elif p == "instagram":
                result = poster.post_to_instagram_api(video_path, caption)
            else:
                result = {"status": "skipped", "error": f"Unknown platform: {p}"}
            result["platform"] = p
            results.append(result)
            log.info(f"[{task_id}] Posted to {p}: {result['status']}")
        except Exception as e:
            results.append({"platform": p, "status": "failed", "error": str(e)})
            log.error(f"[{task_id}] Post to {p} failed: {e}")

    return results

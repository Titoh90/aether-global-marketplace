"""
content_pipeline_executor.py — Full Content Pipeline: Research → Video → Post

Trigger: hermes_core.classify() detects "crea video [producto] amazon" →
         pipeline="content_pipeline", action="research_and_create"

Flow:
  1. research_executor.research_product()   → ProductBrief
  2. Format enriched script_brief from brief
  3. mediafactory_executor.generate_and_post() → video MP4
  4. (optional) auto-post to TikTok/Instagram

Returns dict with fields expected by gateway _execute_task:
  {"status", "output_path", "brief", "research_ok", "research_source", "post_results", "summary"}
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

OPERATOR_ROOT = Path(__file__).resolve().parents[1]
if str(OPERATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(OPERATOR_ROOT))

from executors import research_executor, mediafactory_executor

log = logging.getLogger("content_pipeline_executor")


def research_and_create(params: dict, task_id: str) -> dict:
    """
    Combines Product Research + Video Generation + Auto-posting into a single atomic task.
    Triggered by `content_pipeline.research_and_create` intent.
    """
    topic = params.get("topic") or params.get("intent", "")
    should_post = params.get("post", "false")

    log.info(f"[{task_id}] Starting full content pipeline for: {topic}")

    # ── 1. Research ────────────────────────────────────────────────────────────
    research_res = research_executor.research_product(topic, task_id)
    if research_res.get("status") != "success":
        return {
            "status": "failed",
            "error": f"Research step failed: {research_res.get('error', 'unknown')}",
        }

    brief = research_res.get("brief", {})
    log.info(f"[{task_id}] Research done: {brief.get('name', '?')} | source={research_res.get('source', '?')}")

    # ── 2. Build enriched script_brief ────────────────────────────────────────
    script_brief = (
        f"Create a viral TikTok/Reels video script for this product:\n"
        f"Product: {brief.get('name', topic)}\n"
        f"Viral Angle: {brief.get('video_angle', 'trending discovery')}\n"
        f"Opening Hook: {brief.get('hook', 'You need to see this')}\n"
        f"Price: ${brief.get('price', 0)}\n"
        f"Hashtags: {', '.join(brief.get('hashtags', [])[:5])}\n\n"
        f"Make the script energetic, focused on the viral angle, and compelling."
    )

    # ── 3. Video Generation ────────────────────────────────────────────────────
    mf_params = {
        "topic": topic,
        "post": should_post,
        "platform": params.get("platform", "both"),
        "script_brief": script_brief,
    }

    mf_res = mediafactory_executor.generate_and_post(mf_params, task_id)
    if mf_res.get("status") != "success":
        return {
            "status": "failed",
            "error": f"Media generation failed: {mf_res.get('error', 'unknown')}",
            "summary": (
                f"{research_res.get('summary')}\n\n"
                f"⚠️ Video generation failed — research data preserved above."
            ),
            "brief": brief,
            "research_ok": True,
            "research_source": research_res.get("source", "unknown"),
        }

    # ── 4. Unified result ─────────────────────────────────────────────────────
    return {
        "status": "success",
        "output_path": mf_res.get("output_path"),
        "brief": brief,
        "research_ok": True,
        "research_source": research_res.get("source", "unknown"),
        "post_results": mf_res.get("post_results", []),
        "summary": (
            f"{research_res.get('summary')}\n\n"
            f"🎬 Video generado: `{mf_res.get('output_path')}`"
        ),
    }

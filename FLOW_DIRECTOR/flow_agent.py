#!/usr/bin/env python3
"""
flow_agent.py — IMPERIO Flow Scene Director Agent
Orchestrator: product brief → ScenePlan → Google Flow → clips

PIPELINE:
  Hermes → flow_agent.py → scene_director.py → flow_operator.py → clips/

USAGE:
  python3 flow_agent.py \
    --product "AI Chatbot Builder" \
    --image assets/product_main.jpg \
    --angle "saves 10 hours/week" \
    --platform TikTok \
    --cta "Try free at link in bio"

  python3 flow_agent.py --plan output/flow_20260517_123456.json  # resume
"""

import argparse
import asyncio
import json
import datetime
import shutil
import sys
from pathlib import Path

# Path setup so operator can import frame_extractor
sys.path.insert(0, str(Path(__file__).parent))

from scene_director import build_scene_plan
from flow_operator import FlowOperator

BASE_DIR     = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FLOW_DIRECTOR")
OUTPUT_DIR   = BASE_DIR / "output"
CLIPS_DIR    = BASE_DIR / "clips"
FRAMES_DIR   = BASE_DIR / "frames"
CAROUSEL_DIR = BASE_DIR / "carousel"
LOGS_DIR     = BASE_DIR / "logs"

# ─── HERMES INTEGRATION INTERFACE ─────────────────────────────────────────────

def from_hermes_input(hermes_data: dict) -> dict:
    """
    Accept input from Hermes revenue router.
    hermes_data expected format:
    {
      "product": "...",
      "product_image": "filename.jpg",
      "marketing_angle": "...",
      "platform": "TikTok",
      "audience": "...",
      "cta": "...",
      "n_scenes": 4
    }
    """
    return {
        "product": hermes_data.get("product", ""),
        "product_image": hermes_data.get("product_image", "product_main.jpg"),
        "angle": hermes_data.get("marketing_angle", ""),
        "platform": hermes_data.get("platform", "TikTok"),
        "audience": hermes_data.get("audience", "general consumers"),
        "cta": hermes_data.get("cta", "Visit us"),
        "n_scenes": hermes_data.get("n_scenes", 4),
    }


# ─── EXECUTION REPORT ─────────────────────────────────────────────────────────

def generate_report(plan: dict, operator_log: list) -> str:
    clips = [s for s in plan["scenes"] if s["status"] == "completed"]
    failed = [s for s in plan["scenes"] if s["status"] != "completed"]

    lines = [
        "# Flow Execution Report",
        f"**Plan ID:** {plan['plan_id']}",
        f"**Video:** {plan['video_title']}",
        f"**Product:** {plan['product']}",
        f"**Platform:** {plan['platform']} | {plan['aspect_ratio']}",
        f"**Generated:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Scene Summary",
        "",
        "| # | Purpose | Status | Clip | Duration |",
        "|---|---------|--------|------|----------|",
    ]
    for s in plan["scenes"]:
        status = "✅" if s["status"] == "completed" else "❌"
        clip = Path(s.get("download_path") or "").name or "—"
        dur = f"{s['duration_s']}s"
        lines.append(f"| {s['scene_id']} | {s['purpose']} | {status} | {clip} | {dur} |")

    lines += [
        "",
        "## Generated Clips",
        "",
    ]
    for s in clips:
        lines.append(f"- `clips/{Path(s.get('download_path','?')).name}` — {s['purpose']}: {s['visual_description']}")

    if failed:
        lines += ["", "## Failed Scenes", ""]
        for s in failed:
            lines.append(f"- Scene {s['scene_id']}: {s.get('error','unknown error')}")

    lines += [
        "",
        "## Next Steps (Pixelle Pipeline)",
        "",
        "```bash",
        "# Combine clips with Pixelle-Video + FFmpeg:",
        f"# Input clips are in: {CLIPS_DIR}",
        "# Scene order: " + " → ".join(f"scene_{s['scene_id']:02d}" for s in plan["scenes"]),
        "```",
        "",
        "## Scene Flow Prompts",
        "",
    ]
    for s in plan["scenes"]:
        lines.append(f"**Scene {s['scene_id']} ({s['purpose']}):**")
        lines.append(f"> {s['flow_prompt']}")
        lines.append("")

    return "\n".join(lines)


# ─── PRE-PHASES: AMAZON RESEARCH + FREE IMAGE GENERATION ─────────────────────

async def _run_pre_phases(plan: dict, args) -> dict:
    """
    Async pre-phases that run BEFORE video generation:
    - Phase 0  (--amazon-search): Open Amazon, search keyword, download product
                                   image + extract title/price/bullets.
    - Phase 1.5 (--image-first):  Generate one FREE image per scene via
                                   Nano Banana (Imagen 4) in Google Flow.
                                   Generated images become video start frames.

    Returns updated plan dict.
    """
    from flow_operator import FlowOperator, ensure_chrome_ready, is_chrome_debug_running

    if not is_chrome_debug_running():
        print("   [pre] Launching Chrome for pre-phases...")
        ensure_chrome_ready()

    op = FlowOperator(plan=plan, no_interactive=getattr(args, "yes", True))
    if not await op.connect():
        print("   [pre] Cannot connect to Chrome CDP — skipping pre-phases")
        return plan

    try:
        # ── Phase 0: Amazon Research ─────────────────────────────────────────
        if getattr(args, "amazon_search", None):
            kw = args.amazon_search
            print(f"\n[Phase 0] Amazon Research: '{kw}'...")
            amazon = await op.research_amazon(kw)

            plan["amazon_data"] = {
                "keyword": kw,
                "title":   amazon.get("title", ""),
                "price":   amazon.get("price", ""),
                "bullets": amazon.get("bullets", []),
            }

            main_img = amazon.get("main_image")
            if main_img and hasattr(main_img, "exists") and main_img.exists():
                plan["product_image"] = main_img.name
                for scene in plan["scenes"]:
                    if scene["scene_id"] == 1:
                        scene["image_input"]  = main_img.name
                        scene["image_source"] = "amazon_product"
                print(f"   Title:  {amazon.get('title','')[:60]}")
                print(f"   Price:  {amazon.get('price', 'N/A')}")
                print(f"   Image:  {main_img.name} ({main_img.stat().st_size//1024}KB)")
            else:
                print("   ⚠️  No product image extracted from Amazon")

        # ── Phase 1.5: FREE Image Generation (Nano Banana) ───────────────────
        if getattr(args, "image_first", False):
            print("\n[Phase 1.5] Generating images — Nano Banana (GRATIS)...")
            CAROUSEL_DIR.mkdir(parents=True, exist_ok=True)
            FRAMES_DIR.mkdir(parents=True, exist_ok=True)

            generated = 0
            for scene in plan["scenes"]:
                sid     = scene["scene_id"]
                prompt  = scene.get("image_prompt", "")
                purpose = scene.get("purpose", "")

                if not prompt:
                    print(f"   Scene {sid}: no image_prompt — skip")
                    continue

                print(f"   Scene {sid} ({purpose}): {prompt[:65]}...")

                # Use product image as reference for scene 1 (style anchor)
                ref_img = None
                if sid == 1:
                    prod = BASE_DIR / "assets" / plan.get("product_image", "product_main.jpg")
                    if prod.exists():
                        ref_img = prod

                imgs = await op.generate_images(
                    prompt=prompt,
                    aspect_ratio=scene.get("aspect_ratio", "9:16"),
                    count=1,
                    out_prefix=f"scene_{sid:02d}",
                    reference_image=ref_img,
                )

                if imgs:
                    best = imgs[0]
                    # Also copy to frames/ so video stage finds it
                    frame_dst = FRAMES_DIR / best.name
                    shutil.copy2(str(best), str(frame_dst))
                    scene["image_generated"] = str(best)
                    scene["image_input"]     = best.name
                    scene["image_source"]    = "generated_image"
                    generated += 1
                    print(f"   ✅ Scene {sid}: {best.name} ({best.stat().st_size//1024}KB)")
                else:
                    print(f"   ⚠️  Scene {sid}: generation failed — keeping original input")

            print(f"\n   Generated {generated}/{len(plan['scenes'])} images")
            print(f"   Carousel: {CAROUSEL_DIR}")

    finally:
        await op.close()

    return plan


# ─── MAIN AGENT ───────────────────────────────────────────────────────────────

def run_agent(args) -> int:
    """Main agent execution. Returns 0 on success."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Phase 1: Load or generate scene plan ──
    if args.plan:
        plan_path = Path(args.plan)
        print(f"\n📂 Loading existing plan: {plan_path}")
        plan = json.loads(plan_path.read_text())
        # Resume: process pending AND previously-failed scenes
        pending = [s for s in plan["scenes"] if s["status"] in ("pending", "failed")]
        if not pending:
            print("   All scenes already completed.")
            return 0
        # Reset failed → pending so operator sees them as retriable
        for s in pending:
            if s["status"] == "failed":
                s["status"] = "pending"
        print(f"   Resuming: {len(pending)} pending/failed scenes")
    else:
        print("\n🎬 FLOW SCENE DIRECTOR AGENT")
        print(f"{'='*50}")
        print("\n[Phase 1] Generating scene plan...")
        print(f"   Product:  {args.product}")
        print(f"   Angle:    {args.angle}")
        print(f"   Platform: {args.platform}")
        print(f"   Scenes:   {args.scenes} × 8s = {args.scenes * 8}s")

        plan = build_scene_plan(
            product=args.product,
            product_image=args.image,
            angle=args.angle,
            platform=args.platform,
            audience=args.audience,
            cta=args.cta,
            n_scenes=args.scenes,
        )

        plan_path = OUTPUT_DIR / f"{plan['plan_id']}.json"
        plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
        print(f"\n💾 Scene plan saved: {plan_path}")
        print("\n   REVIEW SCENE PLAN BEFORE CONTINUING:")
        for s in plan["scenes"]:
            print(f"   [{s['scene_id']}] {s['purpose']:10s} ← {s['image_input']}")
            print(f"         PROMPT: {s['flow_prompt'][:80]}...")
        print()

        if not args.yes:
            confirm = input("\n⚡ Start Google Flow generation? [y/N] ").strip().lower()
            if confirm != "y":
                print("Aborted. Scene plan saved. Run with --plan to resume.")
                return 0

        # ── Phase 0 + 1.5: Amazon Research + FREE Image Generation ──────────
        if args.amazon_search or args.image_first:
            print(f"\n[Pre-phases] Amazon={bool(args.amazon_search)} Images={args.image_first}")
            try:
                plan = asyncio.run(_run_pre_phases(plan, args))
                plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))
                print(f"\n   Plan updated with pre-phase data: {plan_path.name}")
            except Exception as e:
                print(f"\n   ⚠️  Pre-phase error: {e}")
                print("   Continuing with original scene plan...")

    # ── Phase 2: Pre-flight checks ──
    print("\n[Phase 2] Pre-flight checks...")

    # Check product image exists
    product_img = BASE_DIR / "assets" / plan.get("product_image", "product_main.jpg")
    if product_img.exists():
        print(f"   ✅ Product image: {product_img}")
    else:
        print(f"   ❌ Product image NOT FOUND: {product_img}")
        print(f"      Place your product image at: {product_img}")
        if not getattr(args, "yes", False):
            input("   Press Enter when image is ready... ")
        else:
            print("   ⚠️  --yes mode: continuing without product image")

    # Check Chrome CDP (Playwright approach — AppleScript is broken)
    from flow_operator import is_chrome_debug_running, ensure_chrome_ready
    if is_chrome_debug_running():
        print("   ✅ Chrome CDP: running on port 9222")
    else:
        print("   ⚠️  Chrome not on port 9222 — launching now...")
        ok = ensure_chrome_ready()
        if ok:
            print("   ✅ Chrome launched on port 9222")
        else:
            print("   ❌ Failed to launch Chrome on port 9222")
            print("      Manual: /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome")
            print("        --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_dbg_root")
            print("        --profile-directory=Default https://labs.google/fx/tools/flow")
            if not args.yes:
                input("   Fix Chrome then press Enter... ")

    # ── Phase 3: Execute scenes in Google Flow ──
    print(f"\n[Phase 3] Executing {plan['total_scenes']} scenes in Google Flow...")

    operator = FlowOperator(
        plan=plan,
        no_interactive=args.yes,
    )

    if args.scene:
        # Single scene mode: filter to just that scene
        plan["scenes"] = [s for s in plan["scenes"] if s["scene_id"] == args.scene]

    use_frames = getattr(args, "frames", False)
    prod_img_for_frames = None
    if use_frames:
        p = BASE_DIR / "assets" / plan.get("product_image", "product_main.jpg")
        prod_img_for_frames = p if p.exists() else None
        print("   --frames mode: generate start+end images before each video")
        if prod_img_for_frames:
            print(f"   Reference image: {prod_img_for_frames.name}")

    plan = FlowOperator.run_sync(
        plan,
        no_interactive=args.yes,
        generate_frames=use_frames,
        product_image=prod_img_for_frames,
    )

    # ── Phase 4: Save results ──
    print("\n[Phase 4] Saving results...")

    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))

    # Execution log
    log_path = LOGS_DIR / f"flow_execution_{plan['plan_id']}.json"
    log_path.write_text(json.dumps({
        "plan_id": plan["plan_id"],
        "execution_log": operator.execution_log,
        "completed": plan.get("completed_scenes", []),
        "failed": plan.get("failed_scenes", []),
    }, indent=2))

    # Report
    report = generate_report(plan, operator.execution_log)
    report_path = OUTPUT_DIR / f"report_{plan['plan_id']}.md"
    report_path.write_text(report)

    completed = len(plan.get("completed_scenes", []))
    total = plan["total_scenes"]

    print(f"   Clips: {completed}/{total} generated")

    # ── Phase 5: TTS + Post-production assembly ──
    if completed > 0:
        print("\n[Phase 5] Running post-production (TTS + FFmpeg assembly)...")
        try:
            from post_producer import run_post_production
            final_video = run_post_production(plan)
            print(f"   Final video: {final_video}")
        except Exception as e:
            print(f"\n  ⚠️  Post-production error: {e}")
            print(f"      Run manually: python3 post_producer.py --plan {plan_path}")
    else:
        print("\n  ⚠️  No clips completed — skipping post-production")
        print("      Run manually after generating clips:")
        print(f"      python3 post_producer.py --plan {plan_path}")

    print(f"\n{'='*50}")
    print("🏁 FLOW AGENT COMPLETE")
    print(f"   Clips:   {completed}/{total} generated")
    print(f"   Clips:   {CLIPS_DIR}")
    print(f"   Report:  {report_path}")
    print(f"   Log:     {log_path}")

    return 0 if completed == total else 1


def main():
    parser = argparse.ArgumentParser(
        description="IMPERIO Flow Scene Director Agent — Google Flow video orchestrator"
    )
    # New run
    parser.add_argument("--product", default="AI Chatbot Builder",
                        help="Product name")
    parser.add_argument("--image", default="product_main.jpg",
                        help="Product image filename (in assets/)")
    parser.add_argument("--angle", default="saves 10 hours per week for businesses",
                        help="Marketing angle")
    parser.add_argument("--platform", default="TikTok",
                        choices=["TikTok", "Reels", "Shorts", "YouTube"])
    parser.add_argument("--audience", default="small business owners")
    parser.add_argument("--cta", default="Try free — link in bio")
    parser.add_argument("--scenes", type=int, default=4, choices=[4, 5])
    # Resume
    parser.add_argument("--plan", default=None,
                        help="Resume from existing scene plan JSON")
    # Execution
    parser.add_argument("--scene", type=int, default=None,
                        help="Run only this scene ID (step-through mode)")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip confirmation prompts")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only generate scene plan, don't open Flow")
    # Expanded pipeline
    parser.add_argument("--amazon-search", default=None, metavar="KEYWORD",
                        help="Research product on Amazon first (screenshot + extract info)")
    parser.add_argument("--image-first", action="store_true",
                        help="Generate FREE start-frame image (Nano Banana) per scene before video")
    parser.add_argument("--frames", action="store_true",
                        help="Generate start+end frame images (Nano Banana FREE) before each Veo 3.1 video"
                             " — enables Fotogramas mode for richer motion control")
    args = parser.parse_args()

    if args.dry_run and not args.plan:
        plan = build_scene_plan(
            product=args.product,
            product_image=args.image,
            angle=args.angle,
            platform=args.platform,
            audience=args.audience,
            cta=args.cta,
            n_scenes=args.scenes,
        )
        out = OUTPUT_DIR / f"{plan['plan_id']}.json"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(plan, indent=2))
        print(f"\n💾 Dry run — plan saved: {out}")
        return

    sys.exit(run_agent(args))


if __name__ == "__main__":
    main()

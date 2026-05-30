#!/usr/bin/env python3
"""
scene_director.py — IMPERIO Flow Scene Director
Converts: product + marketing angle → ScenePlan for Google Flow

Uses Ollama (local) for narrative generation.
Output: scene_plan.json ready for flow_operator.py
"""

import argparse
import json
import re
import httpx
import datetime
from pathlib import Path

OLLAMA_URL = "http://127.0.0.1:11434"
OLLAMA_MODEL = "qwen2.5:1.5b"   # fast; switch to gemma3:12b for quality

OUTPUT_DIR = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FLOW_DIRECTOR/output")
ASSETS_DIR = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FLOW_DIRECTOR/assets")

# ─── FLOW PROMPT ENGINE ──────────────────────────────────────────────────────

CINEMATIC_BASE = (
    "cinematic product advertisement, ultra realistic, high detail, "
    "dynamic lighting, focused on {product}, commercial style, 4K, "
    "smooth motion, advertising shot, premium aesthetic"
)

SCENE_MODIFIERS = {
    "HOOK":       "dramatic opening, close-up impact shot, product reveal moment",
    "FEATURE":    "detailed product functionality demonstration, slow-motion texture reveal",
    "LIFESTYLE":  "real world usage, human interaction, authentic environment, warm tones",
    "EMOTION":    "emotional close, lifestyle aspiration, brand highlight, golden hour",
    "CTA":        "brand identity close-up, cinematic fade out, logo reveal, premium feel",
}

# For Veo 3.1 start+end frame generation (Fotogramas mode)
# start = opening state of the scene, end = conclusion/result state
SCENE_START_PROMPTS = {
    "HOOK":      "product package displayed prominently, dramatic reveal angle, dynamic lighting",
    "FEATURE":   "product being picked up, feature demonstration beginning, hands holding product",
    "LIFESTYLE": "person reaching toward product, daily routine moment, natural setting",
    "EMOTION":   "close-up of skin texture showing concern, before-state composition, soft lighting",
    "CTA":       "product centered in frame, brand colors prominent, cinematic composition",
}
SCENE_END_PROMPTS = {
    "HOOK":      "product fully revealed, audience captured attention, compelling angle closeup",
    "FEATURE":   "feature fully demonstrated, visible result, product highlighted in action",
    "LIFESTYLE": "person using product with satisfaction, authentic lifestyle moment complete",
    "EMOTION":   "radiant glowing skin transformation, after-state, luminous healthy complexion",
    "CTA":       "product and call-to-action clear, purchase intent moment, premium brand feel",
}

PLATFORM_SPECS = {
    "TikTok":  {"aspect": "9:16", "duration_s": 8, "energy": "high energy, fast cuts"},
    "Reels":   {"aspect": "9:16", "duration_s": 8, "energy": "trendy, vibrant movement"},
    "Shorts":  {"aspect": "9:16", "duration_s": 8, "energy": "punchy, immediate hook"},
    "YouTube": {"aspect": "16:9", "duration_s": 8, "energy": "cinematic, wide shots"},
}

SCENE_SEQUENCE_4 = ["HOOK", "FEATURE", "LIFESTYLE", "EMOTION"]
SCENE_SEQUENCE_5 = ["HOOK", "FEATURE", "LIFESTYLE", "EMOTION", "CTA"]

# ─── LLM SCENE GENERATION ────────────────────────────────────────────────────

SCENE_PROMPT = '''Generate a cinematic video ad scene plan for Google Flow.

Product: {product}
Marketing angle: {angle}
Platform: {platform}
Target audience: {audience}
CTA: {cta}

Output ONLY valid JSON, no markdown:
{{
  "video_title": "short catchy title",
  "scenes": [
    {{
      "scene_id": 1,
      "purpose": "HOOK",
      "visual_description": "What the camera sees (20 words max, present tense)",
      "flow_prompt_suffix": "specific visual action or motion in 10 words",
      "narrative_beat": "what emotion/message this scene conveys"
    }}
  ]
}}

Rules:
- Exactly {n_scenes} scenes
- Purposes in order: {purposes}
- Each visual_description must mention the product or product context
- flow_prompt_suffix is the MOTION DESCRIPTION only (no product name, just action)
- Keep all text in English regardless of input language
'''


def generate_scene_narrative(product: str, angle: str, platform: str,
                              audience: str, cta: str, n_scenes: int = 4) -> dict:
    purposes = SCENE_SEQUENCE_4 if n_scenes == 4 else SCENE_SEQUENCE_5
    prompt = SCENE_PROMPT.format(
        product=product, angle=angle, platform=platform,
        audience=audience, cta=cta,
        n_scenes=n_scenes, purposes=", ".join(purposes)
    )

    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{OLLAMA_URL}/api/generate", json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.75, "num_predict": 1000}
        })
        resp.raise_for_status()

    raw = resp.json()["response"]
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON in LLM response:\n{raw[:400]}")
    return json.loads(match.group())


# ─── SCENE PLAN BUILDER ───────────────────────────────────────────────────────

def build_scene_plan(
    product: str,
    product_image: str,
    angle: str,
    platform: str = "TikTok",
    audience: str = "general consumers",
    cta: str = "Visit our website",
    n_scenes: int = 4,
) -> dict:

    spec = PLATFORM_SPECS.get(platform, PLATFORM_SPECS["TikTok"])
    purposes = SCENE_SEQUENCE_4[:n_scenes] if n_scenes <= 4 else SCENE_SEQUENCE_5

    print(f"  Generating narrative via Ollama ({OLLAMA_MODEL})...")
    narrative = generate_scene_narrative(
        product, angle, platform, audience, cta, n_scenes
    )

    scenes = []
    for i, (scene_data, purpose) in enumerate(zip(narrative["scenes"], purposes), 1):

        # Build Google Flow prompt
        base = CINEMATIC_BASE.format(product=product)
        modifier = SCENE_MODIFIERS[purpose]
        energy = spec["energy"]
        suffix = scene_data.get("flow_prompt_suffix", "")
        flow_prompt = f"{base}, {modifier}, {energy}, {suffix}".strip().rstrip(",")

        # Input image logic: first scene uses product image, others use last frame
        if i == 1:
            image_input = product_image
            image_source = "product_image"
        else:
            image_input = f"scene_{i-1:02d}_last_frame.png"
            image_source = "last_frame_extract"

        # Image generation prompts (Nano Banana / Imagen 4 — FREE)
        # Shorter, visual, product-focused (for still image)
        visual_desc = scene_data.get('visual_description', '')
        image_prompt = (
            f"professional product photography of {product}, "
            f"{purpose.lower()} scene, "
            f"{visual_desc}, "
            f"studio lighting, commercial quality, {spec['aspect']} format, "
            f"clean background, high resolution"
        ).strip()

        # Start frame: opening visual (HOW the scene begins)
        start_base = SCENE_START_PROMPTS.get(purpose, "product featured prominently")
        start_frame_prompt = (
            f"professional product ad photography, {product}, "
            f"{start_base}, "
            f"{visual_desc}, "
            f"{spec['aspect']} vertical format, cinematic commercial lighting, 4K, "
            f"ultra realistic, product must be clearly visible and identifiable"
        ).strip()

        # End frame: conclusion visual (HOW the scene ends/transforms)
        end_base = SCENE_END_PROMPTS.get(purpose, "transformation complete, product visible")
        end_frame_prompt = (
            f"professional product ad photography, {product}, "
            f"{end_base}, "
            f"{visual_desc}, "
            f"{spec['aspect']} vertical format, cinematic commercial lighting, 4K, "
            f"ultra realistic, product must be clearly visible and identifiable"
        ).strip()

        scene = {
            "scene_id": i,
            "duration_s": spec["duration_s"],
            "purpose": purpose,
            "aspect_ratio": spec["aspect"],

            # Narrative
            "visual_description": visual_desc,
            "narrative_beat": scene_data.get("narrative_beat", ""),

            # Image generation (FREE — Nano Banana)
            "image_prompt": image_prompt,           # generic (fallback)
            "start_frame_prompt": start_frame_prompt,  # opening state
            "end_frame_prompt": end_frame_prompt,      # conclusion state
            "image_generated": None,  # filled after image generation

            # Google Flow video inputs
            "flow_prompt": flow_prompt,
            "image_input": image_input,
            "image_source": image_source,
            "model": "Veo 3.1",
            "use_frames_mode": True,

            # Output spec
            "output_clip": f"scene_{i:02d}_{purpose.lower()}.mp4",
            "last_frame_output": f"scene_{i:02d}_last_frame.png",
            "transition_out": "final_render" if i == n_scenes else "frame_extract",

            # Execution state
            "status": "pending",
            "flow_url": None,
            "download_path": None,
        }
        scenes.append(scene)

    plan = {
        "plan_id": f"flow_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "created_at": datetime.datetime.now().isoformat(),
        "product": product,
        "product_image": product_image,
        "marketing_angle": angle,
        "platform": platform,
        "audience": audience,
        "cta": cta,
        "video_title": narrative.get("video_title", f"{product} — {angle}"),
        "total_scenes": n_scenes,
        "total_duration_s": n_scenes * spec["duration_s"],
        "aspect_ratio": spec["aspect"],
        "scenes": scenes,
        "execution_log": [],
    }

    return plan


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Flow Scene Director — converts product brief into Google Flow scene plan"
    )
    parser.add_argument("--product", default="AI Chatbot Builder",
                        help="Product name")
    parser.add_argument("--image", default="product_main.jpg",
                        help="Product reference image filename (in assets/)")
    parser.add_argument("--angle", default="saves 10 hours per week for businesses",
                        help="Marketing angle / key benefit")
    parser.add_argument("--platform", default="TikTok",
                        choices=["TikTok", "Reels", "Shorts", "YouTube"])
    parser.add_argument("--audience", default="small business owners and entrepreneurs")
    parser.add_argument("--cta", default="Try free at link in bio")
    parser.add_argument("--scenes", type=int, default=4, choices=[4, 5])
    parser.add_argument("--model", default=None,
                        help="Ollama model to use")
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    global OLLAMA_MODEL
    if args.model:
        OLLAMA_MODEL = args.model

    print("\n🎬 FLOW SCENE DIRECTOR")
    print(f"{'='*50}")
    print(f"Product:   {args.product}")
    print(f"Image:     {args.image}")
    print(f"Angle:     {args.angle}")
    print(f"Platform:  {args.platform}")
    print(f"Scenes:    {args.scenes} × 8s")

    print("\n[1/2] Building scene plan...")
    plan = build_scene_plan(
        product=args.product,
        product_image=args.image,
        angle=args.angle,
        platform=args.platform,
        audience=args.audience,
        cta=args.cta,
        n_scenes=args.scenes,
    )

    print("\n[2/2] Saving scene plan...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.output) if args.output else OUTPUT_DIR / f"{plan['plan_id']}.json"
    out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False))

    print(f"\n📋 SCENE PLAN: {plan['video_title']}")
    print(f"   Plan ID: {plan['plan_id']}")
    print(f"   Scenes:  {plan['total_scenes']} × {plan['scenes'][0]['duration_s']}s = {plan['total_duration_s']}s total")
    print(f"   Format:  {plan['aspect_ratio']}")
    print()
    for scene in plan['scenes']:
        print(f"   [{scene['scene_id']}] {scene['purpose']:10s} | "
              f"input: {scene['image_input'][:30]}")
        print(f"         → {scene['flow_prompt'][:80]}...")
        print()

    print(f"💾 Saved: {out_path}")
    print(f"\n⚡ Next: python3 flow_operator.py --plan {out_path}")

    return plan


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
LTX-Video v0.9.1 local inference test — optimized for M4 16GB RAM
Uses sequential CPU offload to handle low available RAM.

Usage:
  python3 ltx_test.py --prompt "A woman applying skincare" --output /tmp/ltx_test.mp4
  python3 ltx_test.py --image /path/to/frame.png --prompt "..." --output /tmp/ltx_test.mp4
"""

import argparse
import os
import time
from pathlib import Path

# Point HF to external disk cache
HF_CACHE = "/Volumes/OPENCLAW_STORAG 1/SYSTEM_CACHES/huggingface"
MODEL_PATH = (
    "/Volumes/OPENCLAW_STORAG 1/SYSTEM_CACHES/huggingface/hub"
    "/models--Lightricks--LTX-Video/snapshots"
    "/8984fa25007f376c1a299016d0957a37a2f797bb"
)
os.environ["HF_HOME"] = HF_CACHE
os.environ["TRANSFORMERS_CACHE"] = HF_CACHE + "/hub"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import torch
from diffusers import LTXImageToVideoPipeline, LTXPipeline
from diffusers.utils import export_to_video
from PIL import Image


def get_available_ram_gb() -> float:
    """Approximate free + inactive RAM on macOS."""
    import subprocess
    out = subprocess.check_output(["vm_stat"]).decode()
    free = inactive = 0
    for line in out.splitlines():
        if "Pages free" in line:
            free = int(line.split()[-1].strip("."))
        if "Pages inactive" in line:
            inactive = int(line.split()[-1].strip("."))
    return (free + inactive) * 4096 / 1_073_741_824


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True, help="Video description prompt")
    parser.add_argument("--negative-prompt", default=(
        "low quality, blurry, distorted, pixelated, artifacts, "
        "watermark, text, bad anatomy, worst quality"
    ))
    parser.add_argument("--image", default=None, help="Start frame (image-to-video)")
    parser.add_argument("--output", default="/tmp/ltx_test.mp4")
    parser.add_argument("--width", type=int, default=480,  help="Width (divisible by 32)")
    parser.add_argument("--height", type=int, default=848, help="Height (divisible by 32) — 9:16 default")
    parser.add_argument("--frames", type=int, default=49,  help="Frame count (8n+1 for LTX)")
    parser.add_argument("--fps", type=int, default=16)
    parser.add_argument("--steps", type=int, default=25,   help="Inference steps (20-50)")
    parser.add_argument("--guidance", type=float, default=7.5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-offload", action="store_true", help="Disable CPU offload (needs 8+ GB free)")
    args = parser.parse_args()

    # Validate dimensions
    assert args.width % 32 == 0,  f"Width must be divisible by 32, got {args.width}"
    assert args.height % 32 == 0, f"Height must be divisible by 32, got {args.height}"
    assert (args.frames - 1) % 8 == 0, f"Frames must be 8n+1, got {args.frames}"

    avail = get_available_ram_gb()
    print(f"[RAM] Available: {avail:.1f} GB")
    use_offload = not args.no_offload
    if avail > 8:
        print("[RAM] Sufficient — disabling CPU offload for speed")
        use_offload = False
    elif not use_offload:
        print("[RAM] WARNING: low RAM + no offload — may crash")

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    dtype = torch.float16
    print(f"[Device] {device} | dtype: {dtype}")
    print(f"[Model] Loading from: {MODEL_PATH}")

    t0 = time.time()

    # Load pipeline
    if args.image:
        print("[Pipeline] Image-to-Video (LTXImageToVideoPipeline)")
        pipe = LTXImageToVideoPipeline.from_pretrained(
            MODEL_PATH,
            torch_dtype=dtype,
            local_files_only=True,
        )
    else:
        print("[Pipeline] Text-to-Video (LTXPipeline)")
        pipe = LTXPipeline.from_pretrained(
            MODEL_PATH,
            torch_dtype=dtype,
            local_files_only=True,
        )

    if use_offload:
        print("[RAM] Enabling sequential CPU offload...")
        pipe.enable_sequential_cpu_offload()
    else:
        pipe = pipe.to(device)

    pipe.enable_attention_slicing()
    print(f"[Load] Pipeline ready in {time.time()-t0:.1f}s")

    # Optional: load start image
    condition_image = None
    if args.image:
        print(f"[Image] Loading start frame: {args.image}")
        img = Image.open(args.image).convert("RGB")
        # Resize to match requested dimensions
        img = img.resize((args.width, args.height), Image.LANCZOS)
        condition_image = img

    generator = torch.manual_seed(args.seed)

    print("\n[Generate]")
    print(f"  Prompt:     {args.prompt[:80]}")
    print(f"  Resolution: {args.width}x{args.height}")
    print(f"  Frames:     {args.frames} @ {args.fps}fps = {args.frames/args.fps:.1f}s")
    print(f"  Steps:      {args.steps} | Guidance: {args.guidance}")
    print(f"  CPU offload: {use_offload}")

    t1 = time.time()

    gen_kwargs = dict(
        prompt=args.prompt,
        negative_prompt=args.negative_prompt,
        width=args.width,
        height=args.height,
        num_frames=args.frames,
        num_inference_steps=args.steps,
        guidance_scale=args.guidance,
        generator=generator,
    )
    if condition_image is not None:
        gen_kwargs["image"] = condition_image

    output = pipe(**gen_kwargs)
    frames = output.frames[0]
    elapsed = time.time() - t1

    # Save video
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    export_to_video(frames, str(out_path), fps=args.fps)

    size_mb = out_path.stat().st_size / 1_048_576
    print(f"\n[Done] Generated in {elapsed:.0f}s")
    print(f"[Output] {out_path} ({size_mb:.1f} MB)")
    print(f"[Stats] {args.frames} frames / {elapsed:.0f}s = {args.frames/elapsed:.2f} fps generation speed")


if __name__ == "__main__":
    main()

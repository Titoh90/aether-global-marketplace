#!/usr/bin/env python3
"""
test_pipeline.py — End-to-end pipeline test (no Google Flow required)

Tests the COMPLETE pipeline EXCEPT Google Flow generation:
1. Load existing scene plan (output/flow_20260517_091356.json)
2. Create MOCK clips with Pillow + FFmpeg (simulating Flow output)
   - 1080x1920 (9:16 vertical), 8s each
   - Each scene: unique color + scene text + zoompan animation
3. Extract last frames from each mock clip (frame_extractor)
4. Run post_producer.run_post_production() → final assembled video
5. Verify final video exists at output/test_final_video.mp4

Run:
  cd "/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FLOW_DIRECTOR"
  python3 test_pipeline.py
"""

import sys
import json
import subprocess
import tempfile
import shutil
from pathlib import Path

# Ensure local imports work
sys.path.insert(0, str(Path(__file__).parent))

BASE_DIR   = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FLOW_DIRECTOR")
PLAN_FILE  = BASE_DIR / "output" / "flow_20260517_091356.json"
CLIPS_DIR  = BASE_DIR / "clips"
FRAMES_DIR = BASE_DIR / "frames"
OUTPUT_DIR = BASE_DIR / "output"

# Scene colors for visual distinction (BGR-ish, but we use ffmpeg color names)
SCENE_COLORS = ["#1a237e", "#1b5e20", "#b71c1c", "#f57f17"]
SCENE_COLOR_NAMES = ["darkblue", "#1b5e20", "darkred", "#f57f17"]


# ─── MOCK CLIP GENERATION ─────────────────────────────────────────────────────

def create_mock_clip(scene: dict, output_path: Path) -> Path:
    """
    Create a mock video clip with Pillow + FFmpeg.
    1080x1920, 8s, smooth zoompan animation, scene text overlay.
    No force_original_aspect_ratio=fill (incompatible with FFmpeg 8.1).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    scene_id = scene["scene_id"]
    purpose  = scene.get("purpose", f"SCENE_{scene_id}")
    duration = scene.get("duration_s", 8)
    color    = SCENE_COLORS[scene_id - 1] if scene_id <= len(SCENE_COLORS) else "#333333"

    # Create base image with Pillow (PNG)
    print(f"    Creating mock image for scene {scene_id}...")
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (1080, 1920), color=_hex_to_rgb(color))
        draw = ImageDraw.Draw(img)

        # Gradient overlay (top to bottom, darker)
        for y in range(1920):
            alpha = int(120 * y / 1920)
            draw.rectangle([(0, y), (1080, y + 1)], fill=(0, 0, 0, alpha))

        # Text
        lines = [
            f"SCENE {scene_id}",
            purpose,
            f"Duration: {duration}s",
            "",
            scene.get("visual_description", "")[:60],
        ]
        y_start = 800
        for i, line in enumerate(lines):
            if not line:
                continue
            size = 72 if i == 0 else 48 if i == 1 else 36
            # Try to load a font, fallback to default
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size)
            except Exception:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), line, font=font)
            w = bbox[2] - bbox[0]
            draw.text(((1080 - w) // 2, y_start + i * (size + 12)), line,
                      fill="white", font=font)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img_path = Path(tmp.name)
        img.save(str(img_path))

    except ImportError:
        print("    [mock] Pillow not available — creating solid color via FFmpeg")
        img_path = None

    # FFmpeg: image → animated video with zoompan
    print(f"    Encoding mock clip scene {scene_id} ({duration}s)...")

    fps = 25
    total_frames = duration * fps

    if img_path and img_path.exists():
        # zoompan: slow zoom in over the duration
        zoompan_expr = (
            f"zoompan=z='if(lte(zoom,1.0),1.0,zoom-0.0015)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={total_frames}:s=1080x1920:fps={fps}"
        )
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(img_path),
            "-vf", zoompan_expr,
            "-t", str(duration),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            str(output_path)
        ]
    else:
        # Pure FFmpeg color source (no Pillow)
        r, g, b = _hex_to_rgb(color)
        color_str = f"0x{r:02x}{g:02x}{b:02x}"
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={color_str}:size=1080x1920:rate={fps}:duration={duration}",
            "-vf", f"drawtext=text='SCENE {scene_id} {purpose}':fontsize=72:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-preset", "ultrafast",
            str(output_path)
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if img_path:
        img_path.unlink(missing_ok=True)

    if result.returncode != 0:
        print(f"    [mock] FFmpeg error:\n{result.stderr[-1000:]}")
        # Last resort: simplest possible clip
        _create_minimal_clip(scene_id, duration, output_path)

    size = output_path.stat().st_size / 1024
    print(f"    Mock clip: {output_path.name} ({size:.0f} KB)")
    return output_path


def _create_minimal_clip(scene_id: int, duration: int, output_path: Path) -> None:
    """Absolute fallback: simplest FFmpeg color video."""
    colors = ["blue", "green", "red", "yellow"]
    color = colors[scene_id - 1] if scene_id <= len(colors) else "gray"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={color}:size=1080x1920:rate=25:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "ultrafast",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert #rrggbb or CSS color name to (r, g, b)."""
    hex_color = hex_color.strip("#")
    if len(hex_color) == 6:
        return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))
    return (100, 100, 200)  # fallback blue


# ─── FRAME EXTRACTION ─────────────────────────────────────────────────────────

def extract_mock_last_frames(plan: dict) -> None:
    """Extract last frame from each mock clip for chain continuity test."""
    from frame_extractor import extract_last_frame

    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    for scene in plan["scenes"]:
        if scene.get("transition_out") == "frame_extract":
            clip_name = scene["output_clip"]
            clip_path = CLIPS_DIR / clip_name
            frame_out = FRAMES_DIR / scene["last_frame_output"]

            if clip_path.exists():
                print(f"    Extracting last frame: {clip_name} → {scene['last_frame_output']}")
                try:
                    extract_last_frame(clip_path, frame_out)
                    print(f"    Frame OK: {frame_out.name}")
                except Exception as e:
                    print(f"    Frame extraction failed: {e}")
            else:
                print(f"    Clip not found for frame extraction: {clip_path}")


# ─── TEST RUNNER ──────────────────────────────────────────────────────────────

def run_test():
    """Full pipeline test."""
    print("\n" + "="*60)
    print("🧪 FLOW DIRECTOR — PIPELINE TEST (no Google Flow)")
    print("="*60)

    # ── Step 1: Load scene plan ─────────────────────────────────────────────
    print(f"\n[Step 1] Loading scene plan: {PLAN_FILE.name}")
    if not PLAN_FILE.exists():
        print(f"ERROR: Plan not found: {PLAN_FILE}")
        print("Run scene_director.py first to generate a plan.")
        sys.exit(1)

    with open(PLAN_FILE) as f:
        plan = json.load(f)

    print(f"  Plan ID:  {plan['plan_id']}")
    print(f"  Product:  {plan['product']}")
    print(f"  Scenes:   {plan['total_scenes']} × {plan['scenes'][0]['duration_s']}s")
    print(f"  Platform: {plan['platform']}")

    # ── Step 2: Create mock clips ───────────────────────────────────────────
    print(f"\n[Step 2] Creating {plan['total_scenes']} mock clips...")
    CLIPS_DIR.mkdir(parents=True, exist_ok=True)

    for scene in plan["scenes"]:
        clip_path = CLIPS_DIR / scene["output_clip"]
        if clip_path.exists():
            print(f"  Clip exists, reusing: {clip_path.name}")
        else:
            create_mock_clip(scene, clip_path)

    print(f"  All mock clips ready in: {CLIPS_DIR}")

    # ── Step 3: Extract last frames ─────────────────────────────────────────
    print(f"\n[Step 3] Extracting last frames from mock clips...")
    try:
        extract_mock_last_frames(plan)
    except Exception as e:
        print(f"  WARNING: Frame extraction error: {e}")
        print("  Continuing — post-production does not require frames.")

    # ── Step 4: Post-production ─────────────────────────────────────────────
    print(f"\n[Step 4] Running post_producer.run_post_production()...")

    from post_producer import run_post_production

    final_output = OUTPUT_DIR / "test_final_video.mp4"

    try:
        final_path = run_post_production(
            plan=plan,
            clips_dir=CLIPS_DIR,
            final_output=final_output,
        )
    except Exception as e:
        print(f"\nERROR in post_production: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ── Step 5: Verify output ───────────────────────────────────────────────
    print(f"\n[Step 5] Verifying output...")

    if not final_path.exists():
        print(f"  ERROR: Final video not found at: {final_path}")
        sys.exit(1)

    size_mb = final_path.stat().st_size / 1024 / 1024

    # Probe with ffprobe
    probe = subprocess.run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", str(final_path)
    ], capture_output=True, text=True)

    has_video = has_audio = False
    duration_s = 0.0
    if probe.returncode == 0:
        try:
            probe_data = json.loads(probe.stdout)
            for stream in probe_data.get("streams", []):
                if stream.get("codec_type") == "video":
                    has_video = True
                    duration_s = float(stream.get("duration", 0))
                elif stream.get("codec_type") == "audio":
                    has_audio = True
        except Exception:
            pass

    print(f"\n{'='*60}")
    print(f"✅ PIPELINE TEST RESULTS")
    print(f"{'='*60}")
    print(f"  Output:     {final_path}")
    print(f"  Size:       {size_mb:.1f} MB")
    print(f"  Duration:   {duration_s:.1f}s (expected {plan['total_duration_s']}s)")
    print(f"  Has video:  {'YES' if has_video else 'NO'}")
    print(f"  Has audio:  {'YES' if has_audio else 'NO (TTS may not be available)'}")
    print()

    if not has_video:
        print("  FAIL: Output video has no video stream")
        sys.exit(1)

    expected_dur = plan["total_duration_s"]
    if abs(duration_s - expected_dur) > 2:
        print(f"  WARNING: Duration mismatch ({duration_s:.1f}s vs expected {expected_dur}s)")
    else:
        print(f"  Duration OK: {duration_s:.1f}s ≈ {expected_dur}s")

    print(f"\n  Pipeline test PASSED. Final video ready.")
    print(f"  Path: {final_path}")
    return final_path


if __name__ == "__main__":
    result = run_test()
    sys.exit(0)

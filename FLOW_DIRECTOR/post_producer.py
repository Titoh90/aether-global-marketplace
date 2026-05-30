#!/usr/bin/env python3
"""
post_producer.py — TTS + FFmpeg assembly for Flow clips
After Google Flow generates clips/, this assembles the final video.

Pipeline:
  clips/scene_01_hook.mp4 + scene_02_feature.mp4 + ... →
  TTS narration per scene →
  FFmpeg concat + audio mix →
  output/final_video.mp4
"""

import asyncio
import json
import subprocess
import sys
import datetime
import tempfile
from pathlib import Path

BASE_DIR   = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FLOW_DIRECTOR")
CLIPS_DIR  = BASE_DIR / "clips"
OUTPUT_DIR = BASE_DIR / "output"
AUDIO_DIR  = BASE_DIR / "output" / "audio"

# Final render destination (create if missing)
REVENUE_VIDEOS_DIR = Path.home() / "IMPERIO_NUCLEO" / "REVENUE" / "videos"

# ─── NARRATION GENERATION ──────────────────────────────────────────────────────

def generate_scene_narration(scene: dict, voice: str = "en-US-AriaNeural") -> str:
    """
    Returns short TTS narration text for a scene (~8s of speech).

    Priority order:
    1. narrative_beat from plan (product-specific, written by LLM) — trimmed to 1 sentence
    2. visual_description trimmed to 70 chars
    3. Purpose-based fallback with product-aware keyword matching
    """
    purpose = scene.get("purpose", "").upper()
    beat    = (scene.get("narrative_beat") or "").strip()
    desc    = (scene.get("visual_description") or "").strip()
    cta     = (scene.get("cta") or "").strip()

    text = ""

    # ── Primary: use narrative_beat directly (product-specific from LLM) ──
    if beat:
        # Take first sentence only (up to . ? ! or 75 chars)
        import re as _re
        m = _re.search(r'^(.{10,75}?[.!?])', beat)
        if m:
            text = m.group(1).strip()
        elif len(beat) <= 80:
            text = beat
        else:
            # Truncate at last space within 75 chars
            text = beat[:75].rsplit(' ', 1)[0].rstrip(' .,') + "."

    # ── Secondary: visual description ──
    if not text and desc:
        text = desc[:70].rsplit(' ', 1)[0].rstrip(' .,') + "."

    # ── Tertiary: purpose-based keyword fallbacks ──
    if not text:
        text = _purpose_fallback(purpose, beat + desc, cta)

    print(f"    [TTS] Scene {scene.get('scene_id','?')} ({purpose}): \"{text}\"")
    return text


def _purpose_fallback(purpose: str, combined: str, cta: str) -> str:
    """Product-agnostic fallbacks with skincare/beauty awareness."""
    c = combined.lower()

    FALLBACKS = {
        "HOOK": [
            ("pore",      "Get zero pores in just 30 seconds."),
            ("skin",      "The secret to flawless skin is here."),
            ("reveal",    "Get ready for your best skin ever."),
            ("instant",   "Instant results. Real transformation."),
        ],
        "FEATURE": [
            ("pad",       "One pad, zero pores. It really works."),
            ("texture",   "Ultra-fine texture for deep pore cleansing."),
            ("tone",      "Tone, smooth, and refine your skin."),
            ("ingredient","Clinically proven ingredients. Visible results."),
        ],
        "LIFESTYLE": [
            ("morning",   "Make it part of your morning glow ritual."),
            ("daily",     "30 seconds every day. Perfect skin every time."),
            ("routine",   "Elevate your skincare routine effortlessly."),
            ("glow",      "Real people, real glow, real results."),
        ],
        "EMOTION": [
            ("confident", "Feel confident in your own skin."),
            ("radiant",   "Radiant, glowing skin — you deserve this."),
            ("transform", "Your skin transformation starts today."),
            ("love",      "Fall in love with your skin again."),
        ],
        "CTA": [
            ("link",      "Tap the link in bio to shop now."),
            ("free",      "Free shipping. Get yours today."),
        ],
    }

    for kw, phrase in FALLBACKS.get(purpose, []):
        if kw in c:
            return phrase

    # Final defaults per purpose
    defaults = {
        "HOOK":      "Your skin will never be the same.",
        "FEATURE":   "See the difference in just one use.",
        "LIFESTYLE": "Built for real results in real life.",
        "EMOTION":   "This is the glow you've been waiting for.",
        "CTA":       "Link in bio. Shop now.",
    }
    return defaults.get(purpose, cta or "Transform your skin today.")


# ─── TTS GENERATION ───────────────────────────────────────────────────────────

def generate_tts_clip(text: str, output_path: Path, voice: str = "es-MX-DaliaNeural",
                      rate: str = "+0%") -> Path:
    """
    Generate TTS audio clip using edge_tts.
    Returns the mp3 output path.

    Uses asyncio.run() since edge_tts is async.
    Falls back to say -o if edge_tts is unavailable.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import edge_tts

        async def _speak():
            communicate = edge_tts.Communicate(text, voice, rate=rate)
            await communicate.save(str(output_path))

        asyncio.run(_speak())
        print(f"    [TTS] Generated: {output_path.name} ({output_path.stat().st_size} bytes)")
        return output_path

    except ImportError:
        print("    [TTS] edge_tts not found — falling back to macOS say")
        # macOS say fallback: generates AIFF, convert to mp3 via ffmpeg
        aiff_path = output_path.with_suffix(".aiff")
        subprocess.run(["say", "-v", "Paulina", "-o", str(aiff_path), text],
                       check=True)
        # Convert AIFF → MP3
        subprocess.run([
            "ffmpeg", "-y", "-i", str(aiff_path),
            "-codec:a", "libmp3lame", "-q:a", "2",
            str(output_path)
        ], check=True, capture_output=True)
        aiff_path.unlink(missing_ok=True)
        return output_path

    except Exception as e:
        print(f"    [TTS] ERROR generating TTS: {e}")
        raise


# ─── VIDEO ASSEMBLY ───────────────────────────────────────────────────────────

def assemble_final_video(plan: dict, clips_dir: Path, audio_dir: Path,
                         output_path: Path) -> Path:
    """
    Concatenate scene clips and mix in TTS audio per scene.

    Steps:
    1. Build FFmpeg concat list from scene clip files
    2. Mix TTS audio tracks at correct time offsets
    3. Add fade in/out
    4. Output final .mp4

    Returns the final video path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    scenes = plan["scenes"]
    total_scenes = len(scenes)

    # ── Collect clip files ──────────────────────────────────────────────────
    clip_files = []
    for s in scenes:
        clip_name = s.get("output_clip", f"scene_{s['scene_id']:02d}.mp4")
        clip_path = clips_dir / clip_name
        if not clip_path.exists():
            raise FileNotFoundError(
                f"Clip not found: {clip_path}\n"
                f"  Run scene generation first or use test_pipeline.py to create mock clips."
            )
        clip_files.append(clip_path)

    print(f"\n  [Assembly] Found {len(clip_files)}/{total_scenes} clips")

    # ── Step 1: Concatenate video clips ────────────────────────────────────
    concat_video = output_path.parent / f"concat_{plan['plan_id']}.mp4"

    # Build concat list file
    concat_list = output_path.parent / "concat_list.txt"
    concat_list.write_text(
        "\n".join(f"file '{str(p)}'" for p in clip_files)
    )

    print(f"  [Assembly] Concatenating {len(clip_files)} clips...")
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(concat_video)
    ], check=True, capture_output=True)

    print(f"  [Assembly] Concat done: {concat_video.name}")

    # ── Step 2: Build audio mix with per-scene TTS at correct offsets ───────
    scene_duration = scenes[0].get("duration_s", 8)

    # Collect TTS audio files
    audio_inputs = []
    filter_parts = []
    audio_idx = 1  # input index (0 = video)

    for i, scene in enumerate(scenes):
        scene_id = scene.get("scene_id", i + 1)
        audio_name = f"scene_{scene_id:02d}_tts.mp3"
        audio_path = audio_dir / audio_name

        if audio_path.exists():
            audio_inputs.append(str(audio_path))
            offset_s = i * scene_duration
            # Delay audio to scene start, pad to full video length
            total_dur = total_scenes * scene_duration
            filter_parts.append(
                f"[{audio_idx}:a]adelay={offset_s * 1000}|{offset_s * 1000},"
                f"apad=whole_dur={total_dur}[a{i}]"
            )
            audio_idx += 1
        else:
            print(f"  [Assembly] No TTS for scene {scene_id} — skipping audio track")

    # ── Step 3: Mix and finalize ────────────────────────────────────────────
    if audio_inputs:
        # Build FFmpeg command with audio inputs and mix filter
        total_dur = total_scenes * scene_duration

        # Fade in/out: 0.5s at start and end
        fade_dur = 0.5
        fade_start = total_dur - fade_dur

        n_audio = len(audio_inputs)
        mix_inputs = "".join(f"[a{i}]" for i in range(n_audio))
        mix_filter = (
            ";".join(filter_parts) +
            f";{mix_inputs}amix=inputs={n_audio}:normalize=0[mixed]"
            f";[0:v]fade=t=in:st=0:d={fade_dur},fade=t=out:st={fade_start}:d={fade_dur}[vout]"
            f";[mixed]afade=t=in:st=0:d={fade_dur},afade=t=out:st={fade_start}:d={fade_dur}[aout]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(concat_video),
        ]
        for ap in audio_inputs:
            cmd += ["-i", ap]
        cmd += [
            "-filter_complex", mix_filter,
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_path)
        ]
    else:
        # No audio — just add fade to video
        total_dur = total_scenes * scene_duration
        fade_dur = 0.5
        fade_start = total_dur - fade_dur
        cmd = [
            "ffmpeg", "-y",
            "-i", str(concat_video),
            "-vf", f"fade=t=in:st=0:d={fade_dur},fade=t=out:st={fade_start}:d={fade_dur}",
            "-c:v", "libx264",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_path)
        ]

    print(f"  [Assembly] Encoding final video with audio mix...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [Assembly] FFmpeg stderr:\n{result.stderr[-2000:]}")
        raise RuntimeError(f"FFmpeg assembly failed (exit {result.returncode})")

    # Cleanup temp files
    concat_video.unlink(missing_ok=True)
    concat_list.unlink(missing_ok=True)

    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"  [Assembly] Final video: {output_path} ({size_mb:.1f} MB)")
    return output_path


# ─── FULL POST-PRODUCTION PIPELINE ────────────────────────────────────────────

def run_post_production(plan: dict, voice: str = "en-US-AriaNeural",
                        clips_dir: Path = None,
                        final_output: Path = None) -> Path:
    """
    Full post-production pipeline:
    1. Generate TTS narration for all scenes
    2. Assemble final video with audio mix

    Returns final video path.
    """
    clips_dir = clips_dir or CLIPS_DIR
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REVENUE_VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

    plan_id = plan.get("plan_id", "flow_video")
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if final_output is None:
        final_output = OUTPUT_DIR / f"final_{plan_id}.mp4"

    print(f"\n{'='*50}")
    print(f"🎧 POST-PRODUCER — {plan.get('video_title', plan_id)}")
    print(f"   Scenes: {plan['total_scenes']} × {plan['scenes'][0].get('duration_s', 8)}s")
    print(f"   Voice:  {voice}")
    print()

    # ── Phase A: Generate TTS for all scenes ───────────────────────────────
    print(f"  [Phase A] Generating TTS narration ({plan['total_scenes']} scenes)...")

    for scene in plan["scenes"]:
        scene_id = scene["scene_id"]
        text = generate_scene_narration(scene, voice=voice)
        audio_out = AUDIO_DIR / f"scene_{scene_id:02d}_tts.mp3"

        try:
            generate_tts_clip(text, audio_out, voice=voice)
            scene["tts_text"] = text
            scene["tts_path"] = str(audio_out)
        except Exception as e:
            print(f"    [TTS] WARNING: Scene {scene_id} TTS failed: {e}")
            scene["tts_text"] = text
            scene["tts_path"] = None

    # ── Phase B: Assemble final video ──────────────────────────────────────
    print(f"\n  [Phase B] Assembling final video...")

    final_path = assemble_final_video(
        plan=plan,
        clips_dir=clips_dir,
        audio_dir=AUDIO_DIR,
        output_path=final_output,
    )

    # Copy to REVENUE/videos/
    revenue_copy = REVENUE_VIDEOS_DIR / f"final_{plan_id}_{ts}.mp4"
    import shutil
    shutil.copy2(str(final_path), str(revenue_copy))
    print(f"  [Revenue] Copied to: {revenue_copy}")

    print(f"\n{'='*50}")
    print(f"✅ POST-PRODUCTION COMPLETE")
    print(f"   Final video: {final_path}")
    print(f"   Revenue copy: {revenue_copy}")

    return final_path


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Post-producer: TTS + FFmpeg assembly")
    parser.add_argument("--plan", required=True, help="Path to scene plan JSON")
    parser.add_argument("--clips-dir", default=None, help="Override clips directory")
    parser.add_argument("--output", default=None, help="Override output path")
    parser.add_argument("--voice", default="en-US-AriaNeural", help="edge_tts voice name")
    args = parser.parse_args()

    plan_path = Path(args.plan)
    if not plan_path.exists():
        print(f"ERROR: Plan not found: {plan_path}")
        sys.exit(1)

    plan = json.loads(plan_path.read_text())
    clips = Path(args.clips_dir) if args.clips_dir else None
    output = Path(args.output) if args.output else None

    final = run_post_production(plan, voice=args.voice,
                                clips_dir=clips, final_output=output)
    print(f"\nResult: {final}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
frame_extractor.py — Extract last frame from video clip for next-scene continuity
Uses FFmpeg. Called after each Google Flow clip download.
"""

import subprocess
import json
from pathlib import Path

CLIPS_DIR  = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FLOW_DIRECTOR/clips")
FRAMES_DIR = Path("/Volumes/OPENCLAW_STORAG 1/IMPERIO_ROOT/FLOW_DIRECTOR/frames")


def get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds via ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json",
         "-show_format", str(video_path)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def extract_last_frame(video_path: Path, output_path: Path, offset_from_end: float = 0.1) -> Path:
    """
    Extract frame from video at (duration - offset_from_end) seconds.
    Default: 0.1s before end to avoid black frames.
    """
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    duration = get_video_duration(video_path)
    timestamp = max(0.0, duration - offset_from_end)

    result = subprocess.run([
        "ffmpeg", "-y",
        "-ss", str(timestamp),
        "-i", str(video_path),
        "-vframes", "1",
        "-q:v", "2",       # high quality JPEG
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        str(output_path)
    ], capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg frame extract failed:\n{result.stderr[-500:]}")

    print(f"  ✅ Last frame extracted: {output_path.name} (at {timestamp:.2f}s/{duration:.2f}s)")
    return output_path


def extract_first_frame(video_path: Path, output_path: Path) -> Path:
    """Extract first frame (for verification / debugging)."""
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([
        "ffmpeg", "-y", "-ss", "0",
        "-i", str(video_path),
        "-vframes", "1", "-q:v", "2",
        str(output_path)
    ], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg first frame failed:\n{result.stderr[-300:]}")
    return output_path


def process_scene_clip(scene_id: int, clip_path: Path) -> Path:
    """Full pipeline: clip → last frame ready for next scene."""
    frame_out = FRAMES_DIR / f"scene_{scene_id:02d}_last_frame.png"
    extract_last_frame(clip_path, frame_out)
    return frame_out


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract last frame from video clip")
    parser.add_argument("video", help="Path to video clip")
    parser.add_argument("--output", default=None, help="Output PNG path")
    parser.add_argument("--scene-id", type=int, default=1)
    args = parser.parse_args()

    video = Path(args.video)
    if args.output:
        out = Path(args.output)
    else:
        out = FRAMES_DIR / f"scene_{args.scene_id:02d}_last_frame.png"

    extract_last_frame(video, out)
    print(f"Frame saved: {out}")

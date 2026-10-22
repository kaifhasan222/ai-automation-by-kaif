"""Scene-by-Scene Video Generator using Kaif's studio photo and free TTS."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from orchestrator.config import ROOT
from orchestrator.ffmpeg_utils import ffmpeg_exe
from orchestrator.free_render import synthesize_tts

log = logging.getLogger("scene_generator")
AVATAR_PHOTO = ROOT / "assets" / "avatars" / "kaif_photo.jpg"


@dataclass
class SceneClip:
    index: int
    kind: str
    headline: str
    spoken_line: str
    sub: str
    audio_path: Path
    video_path: Path
    duration: float
    start_sec: float
    end_sec: float
    broll_query: str = ""
    broll_path: Path | None = None


def get_audio_duration(path: Path) -> float:
    ff = ffmpeg_exe()
    probe = subprocess.run([ff, "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe.stderr)
    if m:
        hh, mm, ss = m.groups()
        return int(hh) * 3600 + int(mm) * 60 + float(ss)
    return 3.0


def make_scene_avatar_video(
    *,
    photo_path: Path,
    audio_path: Path,
    out_video: Path,
    duration: float,
    camera_style: str = "zoom_in",
    width: int = 720,
    height: int = 1280,
    fps: int = 30,
) -> Path:
    """Render a 9:16 talking-head clip from Kaif's studio photo + audio with subtle camera motion."""
    ff = ffmpeg_exe()
    out_video.parent.mkdir(parents=True, exist_ok=True)

    # Different cinematic camera movements for each scene:
    # zoom_in: Slow subtle punch-in (1.0 -> 1.08)
    # zoom_out: Slow pull-back (1.08 -> 1.0)
    # steady: Clean locked-off camera with subtle micro-scale
    if camera_style == "zoom_in":
        vf = (
            f"scale={width}:{height},"
            f"zoompan=z='min(zoom+0.0004,1.08)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={width}x{height}:fps={fps}"
        )
    elif camera_style == "zoom_out":
        vf = (
            f"scale={width}:{height},"
            f"zoompan=z='max(1.08-0.0004*on,1.0)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={width}x{height}:fps={fps}"
        )
    else:
        vf = (
            f"scale={width}:{height},"
            f"zoompan=z='1.03':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d=1:s={width}x{height}:fps={fps}"
        )

    cmd = [
        ff,
        "-y",
        "-loop",
        "1",
        "-i",
        str(photo_path),
        "-i",
        str(audio_path),
        "-vf",
        vf,
        "-t",
        f"{duration:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        str(out_video),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        log.error("FFmpeg avatar video failed: %s", proc.stderr[-800:])
        raise RuntimeError(f"FFmpeg error: {proc.stderr[-500:]}")

    return out_video


async def generate_scene_pack(
    scenes: list[dict[str, Any]],
    work_dir: Path,
    photo_path: Path | None = None,
) -> list[SceneClip]:
    """Generate TTS voiceover and avatar video clips for all scenes in the script."""
    photo = photo_path or AVATAR_PHOTO
    if not photo.exists():
        raise FileNotFoundError(f"Avatar photo not found at: {photo}")

    work_dir.mkdir(parents=True, exist_ok=True)
    audio_dir = work_dir / "audio"
    video_dir = work_dir / "videos"
    audio_dir.mkdir(exist_ok=True)
    video_dir.mkdir(exist_ok=True)

    clips: list[SceneClip] = []
    current_time = 0.0

    camera_styles = ["zoom_in", "steady", "zoom_out", "zoom_in", "steady", "zoom_in"]

    for i, sc in enumerate(scenes):
        idx = i + 1
        kind = sc.get("kind", "point")
        headline = sc.get("headline", "")
        sub = sc.get("sub", "")
        spoken_line = sc.get("line") or sc.get("script") or headline or "Next update."
        bquery = sc.get("broll_query", "")

        # 1. Synthesize audio
        audio_file = audio_dir / f"scene_{idx:02d}.mp3"
        await synthesize_tts(spoken_line, audio_file)

        # 2. Measure duration
        dur = get_audio_duration(audio_file)
        dur = max(1.8, dur + 0.3)  # add slight breathing space

        # 3. Render video clip
        cam_style = camera_styles[i % len(camera_styles)]
        video_file = video_dir / f"scene_{idx:02d}.mp4"
        await asyncio.to_thread(
            make_scene_avatar_video,
            photo_path=photo,
            audio_path=audio_file,
            out_video=video_file,
            duration=dur,
            camera_style=cam_style,
        )

        clip = SceneClip(
            index=idx,
            kind=kind,
            headline=headline,
            spoken_line=spoken_line,
            sub=sub,
            audio_path=audio_file,
            video_path=video_file,
            duration=round(dur, 2),
            start_sec=round(current_time, 2),
            end_sec=round(current_time + dur, 2),
            broll_query=bquery,
        )
        clips.append(clip)
        current_time += dur

    return clips

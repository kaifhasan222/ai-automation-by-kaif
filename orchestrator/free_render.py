"""Free Mac-side demo: edge-TTS audio + your 9:16 face video (no GPU lip-sync yet)."""

from __future__ import annotations

import asyncio
import re
import subprocess
import uuid
from pathlib import Path

from orchestrator.assets import load_assets
from orchestrator.config import ROOT
from orchestrator.elevenlabs_tts import elevenlabs_configured, synthesize_elevenlabs
from orchestrator.ffmpeg_utils import ffmpeg_exe


def _safe_name(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip())[:40].strip("_")
    return slug or "demo"


def _macos_say_tts(script: str, out_mp3: Path, voice: str | None = None) -> Path:
    """Offline free TTS via macOS `say` (fallback when Edge TTS is blocked)."""
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    aiff = out_mp3.with_suffix(".aiff")
    cmd = ["say", "-o", str(aiff)]
    if voice:
        cmd.extend(["-v", voice])
    cmd.append(script)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"macOS say failed: {proc.stderr or proc.stdout}")

    ffmpeg = ffmpeg_exe()
    conv = subprocess.run(
        [ffmpeg, "-y", "-i", str(aiff), "-ac", "1", "-ar", "24000", str(out_mp3)],
        capture_output=True,
        text=True,
    )
    aiff.unlink(missing_ok=True)
    if conv.returncode != 0:
        raise RuntimeError(f"say->mp3 failed: {conv.stderr[-400:]}")
    return out_mp3


def _pick_macos_voice() -> str | None:
    """Prefer an Indian-English / Hindi system voice if installed."""
    proc = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
    lines = (proc.stdout or proc.stderr or "").splitlines()
    preferred = (
        "Lekha",
        "Veena",
        "Rishi",
        "Sangeeta",
        "Neel",
        "Isha",
        "Samantha",
    )
    available = {ln.split()[0] for ln in lines if ln.strip()}
    for name in preferred:
        if name in available:
            return name
    return None


async def synthesize_tts(script: str, out_mp3: Path, voice: str = "hi-IN-MadhurNeural") -> Path:
    """TTS order: ElevenLabs (if key) → Edge → macOS say."""
    out_mp3.parent.mkdir(parents=True, exist_ok=True)

    if elevenlabs_configured():
        try:
            return await synthesize_elevenlabs(script, out_mp3)
        except Exception as exc:  # noqa: BLE001
            print(f"elevenlabs unavailable ({exc!r}), falling back")

    try:
        import edge_tts

        communicate = edge_tts.Communicate(script, voice)
        await communicate.save(str(out_mp3))
        if out_mp3.exists() and out_mp3.stat().st_size > 1000:
            return out_mp3
    except Exception as exc:  # noqa: BLE001
        print(f"edge-tts unavailable ({exc!r}), falling back to macOS say")

    mac_voice = _pick_macos_voice()
    return await asyncio.to_thread(_macos_say_tts, script, out_mp3, mac_voice)


def mux_avatar_with_audio(
    *,
    audio_path: Path,
    output_mp4: Path,
    max_seconds: float = 58.0,
) -> Path:
    """Mute original video audio, loop/trim video to TTS length, mux new audio."""
    assets = load_assets()
    if assets.missing():
        raise RuntimeError(f"Missing assets: {assets.missing()}")

    ffmpeg = ffmpeg_exe()
    output_mp4.parent.mkdir(parents=True, exist_ok=True)

    # Probe audio duration via ffmpeg stderr
    probe = subprocess.run(
        [ffmpeg, "-i", str(audio_path)],
        capture_output=True,
        text=True,
    )
    dur = 30.0
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe.stderr)
    if m:
        h, mi, s = m.groups()
        dur = int(h) * 3600 + int(mi) * 60 + float(s)
    dur = min(dur, max_seconds)

    # Telegram-friendly encode: 720x1280 @ 30fps keeps uploads under ~8–12MB
    cmd = [
        ffmpeg,
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        str(assets.avatar_video),
        "-i",
        str(audio_path),
        "-t",
        f"{dur:.3f}",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-vf",
        "scale=720:1280:force_original_aspect_ratio=decrease,"
        "pad=720:1280:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "28",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_mp4),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg mux failed:\n{proc.stderr[-800:]}")
    return output_mp4


def compress_for_telegram(src: Path, dst: Path | None = None) -> Path:
    """Re-encode an existing big MP4 so Telegram upload won't time out."""
    ffmpeg = ffmpeg_exe()
    dst = dst or src.with_name(src.stem + "_tg.mp4")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(src),
        "-vf",
        "scale=720:1280:force_original_aspect_ratio=decrease,"
        "pad=720:1280:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "28",
        "-c:a",
        "aac",
        "-b:a",
        "96k",
        "-movflags",
        "+faststart",
        str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"compress failed:\n{proc.stderr[-800:]}")
    return dst


async def render_free_demo(script: str, title: str = "demo") -> Path:
    job = uuid.uuid4().hex[:8]
    out_dir = ROOT / "outputs" / job
    out_dir.mkdir(parents=True, exist_ok=True)
    audio = out_dir / "tts.mp3"
    video = out_dir / f"{_safe_name(title)}.mp4"

    # Keep shorts-friendly length
    text = script.strip()
    if len(text) > 900:
        text = text[:900].rsplit(" ", 1)[0] + "…"

    await synthesize_tts(text, audio)
    # ffmpeg is sync/CPU heavy — run in thread
    await asyncio.to_thread(
        lambda: mux_avatar_with_audio(audio_path=audio, output_mp4=video)
    )
    return video

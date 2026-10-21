"""Build a 9:16 talking-avatar clip from a still photo + voice audio (Mac/free)."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

from orchestrator.config import ROOT
from orchestrator.ffmpeg_utils import ffmpeg_exe


def _make_portrait_still(photo: Path, out_png: Path, size=(1080, 1920)) -> Path:
    w, h = size
    img = Image.open(photo).convert("RGB")

    # Soft blurred fill background from photo
    bg = img.copy()
    bg = ImageEnhance.Brightness(bg).enhance(0.35)
    bg = ImageEnhance.Color(bg).enhance(0.7)
    bg = bg.resize((w, h), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(28))

    canvas = Image.new("RGB", (w, h), (8, 12, 28))
    canvas.paste(bg, (0, 0))

    # Dark blue overlay for tech look
    overlay = Image.new("RGBA", (w, h), (5, 20, 60, 90))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")

    # Fit subject into upper/mid frame (talking-head crop)
    target_h = int(h * 0.72)
    target_w = int(w * 0.92)
    img_ratio = img.width / img.height
    box_ratio = target_w / target_h
    if img_ratio > box_ratio:
        new_h = target_h
        new_w = int(new_h * img_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / img_ratio)
    face = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Center-ish crop toward upper body
    left = max(0, (new_w - target_w) // 2)
    top = max(0, int((new_h - target_h) * 0.15))
    face = face.crop((left, top, left + target_w, top + target_h))

    # Soft rounded card
    card = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    mask = Image.new("L", (target_w, target_h), 0)
    draw = ImageDraw.Draw(mask)
    radius = 48
    draw.rounded_rectangle((0, 0, target_w - 1, target_h - 1), radius=radius, fill=255)
    card.paste(face, (0, 0))
    card.putalpha(mask)

    x = (w - target_w) // 2
    y = int(h * 0.10)
    canvas_rgba = canvas.convert("RGBA")
    canvas_rgba.paste(card, (x, y), card)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas_rgba.convert("RGB").save(out_png, quality=95)
    return out_png


def build_photo_avatar(
    *,
    photo: Path,
    voice: Path,
    output: Path,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> Path:
    tmp = ROOT / "outputs" / "_photo_avatar"
    tmp.mkdir(parents=True, exist_ok=True)
    still = tmp / "portrait_still.jpg"
    _make_portrait_still(photo, still, size=(width, height))

    # Probe duration
    import re

    ff = ffmpeg_exe()
    probe = subprocess.run([ff, "-i", str(voice)], capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe.stderr)
    dur = 10.0
    if m:
        hh, mm, ss = m.groups()
        dur = int(hh) * 3600 + int(mm) * 60 + float(ss)
    frames = max(int(dur * fps), fps * 3)

    # Ken Burns slow zoom while playing voice
    vf = (
        f"scale={width}:{height},"
        f"zoompan=z='min(1.0+0.00045*on,1.12)':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d=1:s={width}x{height}:fps={fps}"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ff,
        "-y",
        "-loop",
        "1",
        "-i",
        str(still),
        "-i",
        str(voice),
        "-vf",
        vf,
        "-t",
        f"{dur:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-1000:])
    return output


if __name__ == "__main__":
    photo = ROOT / "assets/avatars/kaif_photo.jpg"
    voice = ROOT / "assets/voice_samples/kaif_raw.mp3"
    out = ROOT / "assets/avatars/kaif_avatar.mp4"
    path = build_photo_avatar(photo=photo, voice=voice, output=out)
    print(path, path.stat().st_size)

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from orchestrator.assets import load_assets
from orchestrator.captions import estimate_word_timings
from orchestrator.config import ROOT
from orchestrator.ffmpeg_utils import ffmpeg_exe
from orchestrator.free_render import synthesize_tts

REMOTION_DIR = ROOT / "editor_engine" / "remotion_template"
PUBLIC_INPUT = REMOTION_DIR / "public" / "input"


def _audio_duration_sec(path: Path) -> float:
    import re

    probe = subprocess.run(
        [ffmpeg_exe(), "-i", str(path)],
        capture_output=True,
        text=True,
    )
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe.stderr)
    if not m:
        return 8.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def prepare_public_inputs(*, face: Path, voice: Path) -> None:
    PUBLIC_INPUT.mkdir(parents=True, exist_ok=True)
    face_dst = PUBLIC_INPUT / "face.mp4"
    voice_dst = PUBLIC_INPUT / "voice.mp3"
    shutil.copy2(face, face_dst)
    # Normalize voice to mp3 for Remotion
    if voice.suffix.lower() == ".mp3":
        shutil.copy2(voice, voice_dst)
    else:
        subprocess.run(
            [
                ffmpeg_exe(),
                "-y",
                "-i",
                str(voice),
                "-ac",
                "1",
                "-ar",
                "44100",
                str(voice_dst),
            ],
            check=True,
            capture_output=True,
        )


async def render_remotion_reel(
    *,
    script: str,
    hook: str = "",
    title: str = "reel",
    brand: str = "AI Kaif",
    composition: str = "GeminiReelPreview",
) -> Path:
    assets = load_assets()
    if assets.missing():
        raise RuntimeError(f"Missing assets: {assets.missing()}")

    job = uuid.uuid4().hex[:8]
    out_dir = ROOT / "outputs" / f"remotion_{job}"
    out_dir.mkdir(parents=True, exist_ok=True)
    tts_path = out_dir / "voice.mp3"

    text = script.strip()
    if len(text) > 900:
        text = text[:900].rsplit(" ", 1)[0] + "…"

    await synthesize_tts(text, tts_path)
    prepare_public_inputs(face=assets.avatar_video, voice=tts_path)

    dur = _audio_duration_sec(tts_path)
    words = estimate_word_timings(text, dur)
    props: dict[str, Any] = {
        "faceVideo": "input/face.mp4",
        "voiceAudio": "input/voice.mp3",
        "whooshAudio": "sfx/whoosh.mp3",
        "popAudio": "sfx/pop.mp3",
        "bgmAudio": "sfx/bgm.mp3",
        "hookText": hook or (words[0]["text"] + "…"),
        "brand": brand,
        "words": words,
    }
    props_path = out_dir / "props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=2))

    out_mp4 = out_dir / f"{title.replace(' ', '_')[:40]}.mp4"
    cmd = [
        "npx",
        "remotion",
        "render",
        "src/index.ts",
        composition,
        str(out_mp4),
        f"--props={props_path}",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(REMOTION_DIR),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Remotion render failed:\n"
            + (proc.stderr or "")[-1200:]
            + "\n"
            + (proc.stdout or "")[-800:]
        )
    if not out_mp4.exists():
        raise RuntimeError("Remotion finished but output missing")
    return out_mp4

from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from orchestrator.config import ROOT, Settings
from orchestrator.ffmpeg_utils import ffmpeg_exe
from orchestrator.free_render import _macos_say_tts, _pick_macos_voice
from orchestrator.openrouter_client import chat_completion

REMOTION_DIR = ROOT / "editor_engine" / "remotion_template"

SYSTEM = (
    "You write original Hinglish short-form animated explainers. "
    "Do not copy any YouTube video. Return ONLY JSON."
)


def _parse_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


async def generate_animated_script(settings: Settings, topic: str) -> dict[str, Any]:
    user = f"""
Topic: {topic}
Language: {settings.content_language}
Make a 20-28 second animated reel. No face, no voice clone.
5 scenes only. Kinds must be: hook, point, diagram, meme, cta.
Each scene needs a short spoken "line" in Roman Hinglish, one sentence, easy to say aloud.
Meme line must be original reaction text, not a copied meme image or catchphrase from a film.
Diagram sub must use arrows like "A → B → C".
startSec and endSec can be 0; the renderer times them to the voice.

JSON:
{{
  "title": "string",
  "caption": "youtube/instagram caption",
  "scenes": [
    {{"kind":"hook","startSec":0,"endSec":4,"headline":"","sub":"","emoji":"🤔","line":"spoken sentence"}}
  ]
}}
""".strip()
    raw = await chat_completion(settings, system=SYSTEM, user=user, temperature=0.6)
    data = _parse_json(raw)
    scenes = data.get("scenes") or []
    if len(scenes) < 3:
        raise RuntimeError("Animated script missing scenes")
    return data


def _duration_seconds(path: Path) -> float:
    probe = subprocess.run([ffmpeg_exe(), "-i", str(path)], capture_output=True, text=True)
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", probe.stderr)
    if not match:
        return 2.5
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _free_line_tts(text: str, out_mp3: Path) -> Path:
    """Free voice only: Google Indian English, then macOS say. No paid APIs."""
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    try:
        from gtts import gTTS

        gTTS(text, lang="en", tld="co.in").save(str(out_mp3))
        if out_mp3.exists() and out_mp3.stat().st_size > 800:
            return out_mp3
    except Exception as exc:  # noqa: BLE001
        print(f"gTTS unavailable ({exc!r}), using macOS say")
    return _macos_say_tts(text, out_mp3, _pick_macos_voice())


def _spoken_line(scene: dict[str, Any]) -> str:
    line = str(scene.get("line") or "").strip()
    if line:
        return line
    parts = [str(scene.get("headline") or "").strip(), str(scene.get("sub") or "").strip()]
    return ". ".join(part for part in parts if part) or "Next point."


def _attach_free_voice(props: dict[str, Any], job: str) -> dict[str, Any]:
    scenes = list(props.get("scenes") or [])
    work = ROOT / "outputs" / f"animated_{job}" / "voice"
    work.mkdir(parents=True, exist_ok=True)
    public_dir = REMOTION_DIR / "public" / "input"
    public_dir.mkdir(parents=True, exist_ok=True)

    silence = work / "gap.mp3"
    gap = subprocess.run(
        [
            ffmpeg_exe(),
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-t",
            "0.45",
            str(silence),
        ],
        capture_output=True,
        text=True,
    )
    if gap.returncode != 0:
        raise RuntimeError(f"silence failed: {(gap.stderr or '')[-300:]}")

    parts: list[Path] = []
    cursor = 0.0
    timed: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes):
        part = work / f"line_{index}.mp3"
        _free_line_tts(_spoken_line(scene), part)
        length = _duration_seconds(part)
        pad = 0.45 if index < len(scenes) - 1 else 0.4
        updated = dict(scene)
        updated["startSec"] = round(cursor, 2)
        updated["endSec"] = round(cursor + length + pad, 2)
        cursor = updated["endSec"]
        timed.append(updated)
        parts.append(part)
        if index < len(scenes) - 1:
            parts.append(silence)

    voice_name = f"narration_{job}.m4a"
    voice_path = public_dir / voice_name
    listing = work / "concat.txt"
    listing.write_text("".join(f"file '{part}'\n" for part in parts))
    mux = subprocess.run(
        [
            ffmpeg_exe(),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(listing),
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            str(voice_path),
        ],
        capture_output=True,
        text=True,
    )
    if mux.returncode != 0 or not voice_path.exists():
        raise RuntimeError(f"voice mux failed: {(mux.stderr or '')[-400:]}")

    return {**props, "scenes": timed, "voiceAudio": f"input/{voice_name}"}


def render_animated(props: dict[str, Any], title: str) -> Path:
    job = uuid.uuid4().hex[:8]
    out_dir = ROOT / "outputs" / f"animated_{job}"
    out_dir.mkdir(parents=True, exist_ok=True)
    props = _attach_free_voice(
        {
            **props,
            "brand": "AI Kaif",
            "whooshAudio": "sfx/whoosh.mp3",
            "popAudio": "sfx/pop.mp3",
            "bgmAudio": "sfx/bgm.mp3",
        },
        job,
    )
    props_path = out_dir / "props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=2))
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", title)[:40].strip("_") or "animated"
    out_mp4 = out_dir / f"{slug}.mp4"
    proc = subprocess.run(
        [
            "npx",
            "remotion",
            "render",
            "src/index.ts",
            "AnimatedReel",
            str(out_mp4),
            f"--props={props_path}",
        ],
        cwd=str(REMOTION_DIR),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not out_mp4.exists():
        raise RuntimeError((proc.stderr or proc.stdout or "render failed")[-900:])
    return out_mp4

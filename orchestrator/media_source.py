"""Media OS for sourcing free SFX and B-Roll videos."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

import httpx

from orchestrator.config import ROOT
from orchestrator.ffmpeg_utils import ffmpeg_exe

log = logging.getLogger("media_source")
SFX_DIR = ROOT / "assets" / "sfx"


def ensure_sfx_library() -> dict[str, Path]:
    """Ensure essential SFX files (whoosh, pop, click, bgm) exist in assets/sfx."""
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    ff = ffmpeg_exe()

    files = {
        "whoosh": SFX_DIR / "whoosh.mp3",
        "pop": SFX_DIR / "pop.mp3",
        "click": SFX_DIR / "click.mp3",
        "bgm": SFX_DIR / "bgm.mp3",
    }

    # Generate synthetic clean SFX if not present
    if not files["whoosh"].exists():
        subprocess.run(
            [
                ff,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anoisesrc=d=0.35:c=white:r=44100",
                "-af",
                "lowpass=f=1200,afade=t=in:st=0:d=0.1,afade=t=out:st=0.2:d=0.15",
                str(files["whoosh"]),
            ],
            capture_output=True,
            check=False,
        )

    if not files["pop"].exists():
        subprocess.run(
            [
                ff,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=800:duration=0.15",
                "-af",
                "afade=t=out:st=0.05:d=0.1",
                str(files["pop"]),
            ],
            capture_output=True,
            check=False,
        )

    if not files["click"].exists():
        subprocess.run(
            [
                ff,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=1200:duration=0.06",
                "-af",
                "afade=t=out:st=0.02:d=0.04",
                str(files["click"]),
            ],
            capture_output=True,
            check=False,
        )

    if not files["bgm"].exists():
        subprocess.run(
            [
                ff,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=180:duration=35",
                "-af",
                "volume=0.04,afade=t=in:st=0:d=1,afade=t=out:st=33:d=2",
                str(files["bgm"]),
            ],
            capture_output=True,
            check=False,
        )

    return files


async def search_free_broll(query: str, out_path: Path, orientation: str = "portrait") -> Path | None:
    """Fetch free stock video for query via Pexels (if key set)."""
    api_key = os.getenv("PEXELS_API_KEY", "").strip()
    if not api_key:
        log.info("PEXELS_API_KEY not set. Skipping external B-roll download for '%s'.", query)
        return None

    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "per_page": 5,
        "orientation": orientation,
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers=headers, params=params)
            if resp.status_code != 200:
                log.warning("Pexels error %s: %s", resp.status_code, resp.text[:120])
                return None
            data = resp.json()
            videos = data.get("videos") or []
            if not videos:
                return None

            # Find HD or 720p/1080p vertical video file link
            video_files = videos[0].get("video_files") or []
            best_link = None
            for vf in video_files:
                if vf.get("width", 0) <= 1080 and vf.get("file_type") == "video/mp4":
                    best_link = vf.get("link")
                    break
            if not best_link and video_files:
                best_link = video_files[0].get("link")

            if not best_link:
                return None

            out_path.parent.mkdir(parents=True, exist_ok=True)
            dl_resp = await client.get(best_link, follow_redirects=True)
            if dl_resp.status_code == 200:
                out_path.write_bytes(dl_resp.content)
                log.info("Downloaded B-roll for '%s' -> %s", query, out_path)
                return out_path
    except Exception as exc:
        log.warning("B-roll download failed: %s", exc)
        return None

    return None

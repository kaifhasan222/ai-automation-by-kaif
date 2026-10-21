from __future__ import annotations

import asyncio
import os
import re
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv

from orchestrator.config import ROOT

load_dotenv(ROOT / ".env")

API = "https://api.heygen.com"
# Digital twin look: "Kaif Hasan -- 1" (portrait)
DEFAULT_AVATAR_ID = "34c22f15a9874fbf89ebd0679bf9e0c6"
# Cloned HeyGen voice named "Kaif Hasan"
DEFAULT_VOICE_ID = "b9b36cf0ca834a10a56657adc84a8ac4"


class HeyGenError(RuntimeError):
    pass


def heygen_configured() -> bool:
    return bool(os.getenv("HEYGEN_API_KEY", "").strip())


def _headers() -> dict[str, str]:
    key = os.getenv("HEYGEN_API_KEY", "").strip()
    if not key:
        raise HeyGenError("HEYGEN_API_KEY missing")
    return {"x-api-key": key, "Content-Type": "application/json"}


def _safe_name(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip())[:40].strip("_")
    return slug or "heygen"


async def create_avatar_video(script: str, title: str = "AI Kaif") -> Path:
    """Render a 9:16 talking video with the user's HeyGen avatar + cloned voice."""
    text = script.strip()
    if len(text) > 1200:
        text = text[:1200].rsplit(" ", 1)[0] + "…"

    payload = {
        "type": "avatar",
        "avatar_id": os.getenv("HEYGEN_AVATAR_ID", "").strip() or DEFAULT_AVATAR_ID,
        "voice_id": os.getenv("HEYGEN_VOICE_ID", "").strip() or DEFAULT_VOICE_ID,
        "script": text,
        "title": title[:80],
        "aspect_ratio": "9:16",
        "resolution": "720p",
        "output_format": "mp4",
        "engine": {"type": "avatar_iv"},
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{API}/v3/videos", headers=_headers(), json=payload)
        if resp.status_code >= 400:
            raise HeyGenError(f"HeyGen create HTTP {resp.status_code}: {resp.text[:500]}")
        body = resp.json()
        data = body.get("data") or body
        video_id = data.get("video_id") or data.get("id")
        if not video_id:
            raise HeyGenError(f"No video_id in response: {str(body)[:400]}")

        video_url = None
        for _ in range(60):
            await asyncio.sleep(5)
            status = await client.get(f"{API}/v3/videos/{video_id}", headers=_headers())
            if status.status_code >= 400:
                raise HeyGenError(f"HeyGen status HTTP {status.status_code}: {status.text[:400]}")
            info = status.json().get("data") or status.json()
            state = str(info.get("status") or info.get("state") or "").lower()
            if state in {"completed", "complete", "success", "succeeded"}:
                video_url = (
                    info.get("video_url")
                    or info.get("url")
                    or (info.get("output") or {}).get("video_url")
                )
                break
            if state in {"failed", "error"}:
                raise HeyGenError(f"HeyGen render failed: {str(info)[:500]}")

        if not video_url:
            raise HeyGenError(f"HeyGen timed out waiting for {video_id}")

        media = await client.get(video_url, timeout=180.0)
        if media.status_code >= 400:
            raise HeyGenError(f"Download failed HTTP {media.status_code}")

    out_dir = ROOT / "outputs" / f"heygen_{uuid.uuid4().hex[:8]}"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{_safe_name(title)}.mp4"
    path.write_bytes(media.content)
    return path

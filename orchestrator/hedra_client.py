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

API = "https://api.hedra.com/v3"


class HedraError(RuntimeError):
    pass


def hedra_configured() -> bool:
    return bool(os.getenv("HEDRA_API_KEY", "").strip())


def _headers(json_body: bool = False) -> dict[str, str]:
    key = os.getenv("HEDRA_API_KEY", "").strip()
    if not key:
        raise HedraError("HEDRA_API_KEY missing")
    headers = {"Authorization": f"Key {key}"}
    if json_body:
        headers["Content-Type"] = "application/json"
    return headers


def _mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".m4a": "audio/mp4",
    }.get(ext, "application/octet-stream")


async def _upload(client: httpx.AsyncClient, path: Path) -> str:
    with path.open("rb") as handle:
        resp = await client.post(
            f"{API}/files",
            headers=_headers(),
            files={"file": (path.name, handle, _mime(path))},
        )
    if resp.status_code >= 400:
        raise HedraError(f"Hedra upload HTTP {resp.status_code}: {resp.text[:300]}")
    url = resp.json().get("url")
    if not url:
        raise HedraError(f"Hedra upload missing url: {resp.text[:200]}")
    return url


def _output_url(info: dict) -> str | None:
    outputs = info.get("outputs") or []
    if isinstance(outputs, list):
        for item in outputs:
            if isinstance(item, dict):
                for key in ("url", "video_url", "download_url"):
                    if item.get(key):
                        return item[key]
    for key in ("video_url", "url"):
        if info.get(key):
            return info[key]
    return None


async def create_talking_video(
    *,
    image: Path,
    audio: Path,
    title: str = "AI Kaif",
    prompt: str = "A person speaking naturally to the camera, subtle head movement, vertical reel.",
) -> Path:
    """Photo + audio → lip-synced 9:16 video via Hedra Avatar (540p to save credits)."""
    if not image.exists():
        raise HedraError(f"Image missing: {image}")
    if not audio.exists():
        raise HedraError(f"Audio missing: {audio}")

    async with httpx.AsyncClient(timeout=120.0) as client:
        image_url = await _upload(client, image)
        audio_url = await _upload(client, audio)
        payload = {
            "input": {
                "prompt": prompt,
                "aspect_ratio": "9:16",
                "resolution": "540p",
                "start_image": {"source": "url", "url": image_url},
                "audio": {"source": "url", "url": audio_url},
            }
        }
        created = await client.post(
            f"{API}/models/hedra-avatar",
            headers=_headers(json_body=True),
            json=payload,
        )
        if created.status_code >= 400:
            raise HedraError(f"Hedra create HTTP {created.status_code}: {created.text[:500]}")
        body = created.json()
        job_id = body.get("job_id") or body.get("id") or (body.get("data") or {}).get("job_id")
        if not job_id:
            raise HedraError(f"No job_id: {str(body)[:300]}")

        video_url = None
        for _ in range(72):
            await asyncio.sleep(5)
            status = await client.get(f"{API}/jobs/{job_id}/status", headers=_headers())
            if status.status_code == 404:
                status = await client.get(f"{API}/jobs/{job_id}", headers=_headers())
            if status.status_code >= 400:
                raise HedraError(f"Hedra status HTTP {status.status_code}: {status.text[:300]}")
            info = status.json()
            data = info.get("data") if isinstance(info.get("data"), dict) else info
            state = str(data.get("status") or data.get("state") or "").upper()
            if state in {"COMPLETED", "COMPLETE", "SUCCEEDED", "SUCCESS"}:
                video_url = _output_url(data) or _output_url(info)
                if not video_url:
                    full = await client.get(f"{API}/jobs/{job_id}", headers=_headers())
                    if full.status_code < 400:
                        video_url = _output_url(full.json())
                break
            if state in {"FAILED", "ERROR", "CANCELLED", "CANCELED"}:
                raise HedraError(f"Hedra failed: {str(data)[:400]}")

        if not video_url:
            raise HedraError(f"Hedra timed out for job {job_id}")

        media = await client.get(video_url, timeout=180.0)
        if media.status_code >= 400:
            raise HedraError(f"Download HTTP {media.status_code}")

    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", title.strip())[:40].strip("_") or "hedra"
    out_dir = ROOT / "outputs" / f"hedra_{uuid.uuid4().hex[:8]}"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug}.mp4"
    path.write_bytes(media.content)
    return path

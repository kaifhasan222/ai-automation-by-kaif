from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

from orchestrator.config import ROOT

load_dotenv(ROOT / ".env")

# Male conversational premade until instant clone is allowed on the key.
DEFAULT_VOICE_ID = "CwhRBWXzGAHq8TQ4Fs17"  # Roger
TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


class ElevenLabsError(RuntimeError):
    pass


def elevenlabs_configured() -> bool:
    return bool(os.getenv("ELEVENLABS_API_KEY", "").strip())


async def synthesize_elevenlabs(script: str, out_mp3: Path) -> Path:
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise ElevenLabsError("ELEVENLABS_API_KEY missing")

    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip() or DEFAULT_VOICE_ID
    text = script.strip()
    if len(text) > 1800:
        text = text[:1800].rsplit(" ", 1)[0] + "…"

    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    headers = {
        "xi-api-key": key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.45,
            "similarity_boost": 0.8,
            "style": 0.25,
            "use_speaker_boost": True,
        },
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            TTS_URL.format(voice_id=voice_id),
            headers=headers,
            json=payload,
        )

    if resp.status_code >= 400:
        raise ElevenLabsError(f"ElevenLabs HTTP {resp.status_code}: {resp.text[:400]}")

    out_mp3.write_bytes(resp.content)
    if out_mp3.stat().st_size < 1000:
        raise ElevenLabsError("ElevenLabs returned empty audio")
    return out_mp3

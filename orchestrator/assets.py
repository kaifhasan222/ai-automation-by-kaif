from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from orchestrator.config import ROOT


@dataclass(frozen=True)
class AssetPack:
    avatar_video: Path
    avatar_photo: Path
    voice_raw: Path
    voice_ref: Path

    def missing(self) -> list[str]:
        out: list[str] = []
        if not self.avatar_photo.exists():
            out.append("avatar_photo")
        return out

    def summary_html(self) -> str:
        miss = self.missing()
        status = "✅ ready" if not miss else f"⚠️ missing: {', '.join(miss)}"
        has_voice = self.voice_ref.exists() or self.voice_raw.exists()
        return (
            "🗂️ <b>Your assets</b>\n\n"
            f"Status: {status}\n"
            f"• Studio Photo: <code>{self.avatar_photo.name}</code> (✅ Loaded)\n"
            f"• Voice reference: {'✅ Custom WAV' if has_voice else '⚡ Free TTS active'}\n"
            f"• Visual Style: 9:16 Tech Studio Set (kaif_tech_news_set.jpg)\n\n"
            "Commands:\n"
            "• /hyper_reel (Studio Photo + Motion Cards + SFX + HyperFrames)\n"
            "• /reel (Remotion/Hedra)\n"
            "• /script (AI Script Research)\n"
        )


def load_assets() -> AssetPack:
    manifest = ROOT / "assets" / "manifest.json"
    if manifest.exists():
        data = json.loads(manifest.read_text())
        return AssetPack(
            avatar_video=ROOT / data["avatar_video"],
            avatar_photo=ROOT / data["avatar_photo"],
            voice_raw=ROOT / data["voice_raw"],
            voice_ref=ROOT / data["voice_ref"],
        )
    return AssetPack(
        avatar_video=ROOT / "assets/avatars/kaif_base.mp4",
        avatar_photo=ROOT / "assets/avatars/kaif_photo.jpg",
        voice_raw=ROOT / "assets/voice_samples/kaif_raw.mp3",
        voice_ref=ROOT / "assets/voice_samples/kaif_ref.wav",
    )

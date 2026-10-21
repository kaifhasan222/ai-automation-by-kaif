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
        for label, path in (
            ("avatar_video", self.avatar_video),
            ("avatar_photo", self.avatar_photo),
            ("voice_raw", self.voice_raw),
            ("voice_ref", self.voice_ref),
        ):
            if not path.exists():
                out.append(label)
        return out

    def summary_html(self) -> str:
        miss = self.missing()
        status = "✅ ready" if not miss else f"⚠️ missing: {', '.join(miss)}"
        return (
            "🗂️ <b>Your assets</b>\n\n"
            f"Status: {status}\n"
            f"• Video: <code>{self.avatar_video.name}</code>\n"
            f"• Photo: <code>{self.avatar_photo.name}</code>\n"
            f"• Voice ref: <code>{self.voice_ref.name}</code>\n\n"
            "Format notes:\n"
            "• Avatar: photo-based 9:16 + your voice ✅\n"
            "• Voice sample: ~48s cleaned WAV ✅\n"
            "• Commands: /reel (Remotion) · /demo (simple)\n"
            "• Real lip-sync avatar: Modal GPU later"
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

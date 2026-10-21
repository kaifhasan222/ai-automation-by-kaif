from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_allowed_user_ids: frozenset[int]
    openrouter_api_key: str
    openrouter_model: str
    content_niche: str
    content_language: str

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN missing in .env")

        raw_ids = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "").strip()
        ids: set[int] = set()
        if raw_ids:
            for part in raw_ids.split(","):
                part = part.strip()
                if part:
                    ids.add(int(part))

        return cls(
            telegram_bot_token=token,
            telegram_allowed_user_ids=frozenset(ids),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", "").strip(),
            openrouter_model=os.getenv("OPENROUTER_MODEL", "openrouter/free").strip(),
            content_niche=os.getenv("CONTENT_NICHE", "AI tools for creators").strip(),
            content_language=os.getenv("CONTENT_LANGUAGE", "Hinglish").strip(),
        )


def get_settings() -> Settings:
    return Settings.from_env()
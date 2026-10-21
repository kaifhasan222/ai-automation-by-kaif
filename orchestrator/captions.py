from __future__ import annotations

import re
from typing import Any


_HIGHLIGHT = {
    "ai",
    "future",
    "gemini",
    "tool",
    "tools",
    "viral",
    "secret",
    "free",
    "fast",
    "mind",
    "blowing",
    "kaif",
    "agent",
    "agents",
    "automation",
}


def estimate_word_timings(script: str, duration_sec: float) -> list[dict[str, Any]]:
    """Rough caption timings when WhisperX is not available yet."""
    tokens = re.findall(r"[\w']+|[!.?…]|🔥|⚡|🚀", script, flags=re.UNICODE)
    words = [t for t in tokens if t.strip()]
    if not words:
        words = ["Hello"]

    # Leave a little tail silence
    usable = max(1.0, duration_sec * 0.92)
    slot = usable / len(words)
    out: list[dict[str, Any]] = []
    t = 0.05
    for w in words:
        start = t
        end = t + slot * 0.92
        clean = re.sub(r"[^\w]", "", w).lower()
        out.append(
            {
                "text": w,
                "startMs": int(start * 1000),
                "endMs": int(end * 1000),
                "highlight": clean in _HIGHLIGHT or w.isupper(),
            }
        )
        t = end + slot * 0.08
    return out

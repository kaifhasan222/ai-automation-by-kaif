from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx

from orchestrator.config import Settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
log = logging.getLogger("openrouter")

# Free models that currently answer (router first, then stable singles)
DEFAULT_FALLBACKS = [
    "openrouter/free",
    "minimax/minimax-m3.1-flash:free",
    "liquid/lfm-2.5-2.6b:free",
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3.5-lightning:free",
    "poolside/laguna-s-2.1:free",
    "xingchen-agi/xing4.0-29b-a4b:free",
    "dots-studio/dots-3-note-preview:free",
]


class OpenRouterError(RuntimeError):
    pass


def _model_chain(settings: Settings) -> list[str]:
    primary = (settings.openrouter_model or "openrouter/free").strip()
    extra = [
        m.strip()
        for m in os.getenv("OPENROUTER_FALLBACK_MODELS", "").split(",")
        if m.strip()
    ]
    chain: list[str] = []
    for m in [primary, *extra, *DEFAULT_FALLBACKS]:
        if m and m not in chain:
            chain.append(m)
    return chain


async def chat_completion(
    settings: Settings,
    *,
    system: str,
    user: str,
    temperature: float = 0.7,
) -> str:
    if not settings.openrouter_api_key:
        raise OpenRouterError("OPENROUTER_API_KEY missing in .env")

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/local/ai-video-automation",
        "X-Title": "ai-video-automation",
    }

    errors: list[str] = []
    async with httpx.AsyncClient(timeout=90.0) as client:
        for model in _model_chain(settings):
            payload: dict[str, Any] = {
                "model": model,
                "temperature": temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
            # retry flaky 500/429 a couple times per model
            for attempt in range(3):
                try:
                    resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)
                except httpx.HTTPError as exc:
                    errors.append(f"{model} network: {exc}")
                    break

                if resp.status_code in (429, 500, 502, 503):
                    msg = f"{model} HTTP {resp.status_code}"
                    errors.append(msg)
                    log.warning("%s (attempt %s)", msg, attempt + 1)
                    await asyncio.sleep(0.8 * (attempt + 1))
                    continue

                if resp.status_code == 401:
                    raise OpenRouterError(
                        "OpenRouter 401 — key invalid.\n"
                        "Create a normal API key at https://openrouter.ai/keys "
                        "(not a management key)."
                    )

                if resp.status_code >= 400:
                    errors.append(f"{model} HTTP {resp.status_code}: {resp.text[:180]}")
                    break

                data = resp.json()
                try:
                    content = data["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError) as exc:
                    raise OpenRouterError(f"Unexpected OpenRouter response: {data}") from exc

                if not content or not str(content).strip():
                    errors.append(f"{model}: empty content")
                    break

                log.info("OpenRouter OK via %s", data.get("model") or model)
                return str(content)

    raise OpenRouterError(
        "OpenRouter free models busy/failing.\n"
        + "\n".join(f"• {e}" for e in errors[-8:])
        + "\n\n2 min baad /reel dobara try karo, ya .env mein paid model set karo."
    )


async def generate_daily_script(settings: Settings, topic_hint: str | None = None) -> dict[str, Any]:
    system = (
        "You are a viral Shorts/Reels scriptwriter. "
        "Return ONLY valid JSON (no markdown fences)."
    )
    topic = topic_hint or f"one high-engagement angle in niche: {settings.content_niche}"
    user = f"""
Write a 45-60 second talking-head script in {settings.content_language}.
Topic: {topic}

JSON schema:
{{
  "title": "string",
  "hook": "first 2 seconds spoken line",
  "script": "full spoken script",
  "caption": "instagram/youtube caption with 5 hashtags",
  "hashtags": ["tag1", "tag2"],
  "broll_cues": [
    {{"at_sec": 0, "query": "stock search query", "note": "what to show"}}
  ]
}}
""".strip()

    raw = await chat_completion(settings, system=system, user=user)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Some free models wrap JSON loosely — try to extract object
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
        return {
            "title": "Draft script",
            "hook": "",
            "script": cleaned,
            "caption": cleaned[:200],
            "hashtags": [],
            "broll_cues": [],
            "raw": raw,
        }

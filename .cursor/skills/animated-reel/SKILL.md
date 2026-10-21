---
name: animated-reel
description: >-
  Builds a free animated 9:16 explainer without a face avatar or cloned voice.
  Use when the user asks for an animated reel, motion graphics, B-roll style
  cards, meme-style text, SFX, or the daily video flow before paid lip-sync.
---

# Animated reel (no avatar)

Voice clone and talking-head avatar stay off until the user funds Hedra or HeyGen. The live presenter path is Google Flow plus a HyperFrames edit. Follow `video-automation` for that. This skill is only the faceless Remotion reel.

## Flow

1. One idea only. Hinglish. Do not copy a YouTube transcript.
2. Script JSON with five scenes: `hook`, `point`, `diagram`, `meme`, `cta`.
3. Render Remotion composition `AnimatedReel` at 720x1280.
4. Send the MP4 on Telegram with `/animate`.

## Assets that are allowed

- Motion background, kinetic text, diagram arrows, original reaction lines, emoji.
- Spoken voice: free gTTS Indian English (`lang=en`, `tld=co.in`). If Google is down, macOS `say`.
- Bundled SFX under the voice: `public/sfx/whoosh.mp3`, `pop.mp3`, `bgm.mp3`.
- Later, Pexels or Pixabay clips only when the user adds an API key.

## Do not

- Download copyrighted meme images, film stills, or celebrity faces.
- Turn the bot on unless the user asks.
- Call Hedra, HeyGen, or ElevenLabs for this path.

## Commands

```bash
cd editor_engine/remotion_template
npx remotion studio src/index.ts
```

Telegram, after the bot is started: `/animate MCP kya hai`

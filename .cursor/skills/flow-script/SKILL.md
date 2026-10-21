---
name: flow-script
description: >-
  Writes a 9:16 Google Flow script before any video is generated. Use when the
  user asks for a script, micro drama, AI news short, scene prompts, or the
  next Flow scene. Locks a real photo when one is attached, keeps each clip to
  8 seconds, and does not open Flow until the user asks to generate.
---

# Flow script

Train this on Unseen Tech’s course [Long Micro Drama AI Video Kaise Banaye](https://www.youtube.com/watch?v=UbRk5IGGjfw). The video’s master prompt is already saved at `__reference/micro_drama_prompt.md`. Follow that file for drama detail. This skill is the short operating list.

Chat with the user in Roman Hinglish. Do not answer in Devanagari.

## Before writing

1. One story only. If they did not name it, pick one real reported item and link the source. Do not invent news.
2. If a photo is attached, that photo is the face. Do not redesign age, hair, beard, or shirt.
3. For every AI or tech-news presenter script, scene 1 attaches `__reference/kaif_tech_news_set.jpg`. That file is the identity and the room. Adult man, early twenties, medium-brown skin, short black beard and moustache, black hair swept to the side, navy blue shirt with a white windowpane check. Dark blue-grey wall, soft light panel from the left, wooden desk, plain black microphone on a short stand. Do not swap in the peach-wall portrait, and do not invent a different set.
4. Adult only. If a prompt would need a minor, school, or “boy,” stop and change the story. Do not reword it to sneak past a filter.
5. Do not open Flow, and do not spend credits, until the user says to generate.
6. If Flow blocks a prompt for reputational risk or misrepresenting current events, stop. Do not reword that claim to slip the filter. Credits should refund. Leave the existing clip.

## Two modes

**Drama.** Recurring cast, locations, Method A or B, narrator hook on scene 1 only. Full rules: `__reference/micro_drama_prompt.md`.

**Presenter.** The user is on camera giving one news item. No second character. No narrator over a silent face. The host speaks every line.

## Every script

- 9:16. Each scene is 8 seconds. Six scenes is 48 seconds. Say the total.
- One speaker and one short line per scene. About 12 to 16 spoken words. Finish the line before the last second.
- Spoken lines in Devanagari Hindi, copied exactly into the video prompt. Do not write the spoken line in Roman Hinglish, because Flow reads that with the wrong sound. Hindi words such as कंट्रोल, सेफ्टी, सिस्टम, and सब्सक्राइब stay in Devanagari. Keep product and channel names in English: Mistral, Voxtral, AI, API, YouTube, Instagram, NEW KAIF AI. Chat with the user stays Roman Hinglish.
- Only scene 1 may say भाई. Later scenes use another word. Do not put भाई in scenes 2 onward.
- Video prompts in English. Repeat the face, shirt, room, and line in every prompt. Do not write “same as before.”
- No burned-in subtitles, no captions, and no background music inside a Flow clip. After the clips exist, add one music bed that matches the mood and stays under the voice. A tech-news short uses a light, hopeful, no-vocal bed.
- Name the emotion in every video prompt. The hook is a little excited: brighter eyes, a small smile, a quicker clear pace. The middle scenes are serious and clear. The last scene is warm and inviting.
- The last scene of every presenter script is this spoken close, exactly: "ऐसा वीडियो देखने के लिए YouTube पर NEW KAIF AI सब्सक्राइब करो, और Instagram फॉलो करो." Do not burn that line into the Flow clip.
- Scene 1 of an AI or tech-news presenter script attaches `__reference/kaif_tech_news_set.jpg` as the identity ingredient. If the user attached a different photo for that script, use the attached photo instead. Later scenes attach the previous clip so the face, shirt, and set stay put.
- Method A: same angle, continue. Method B: new angle, say which still to attach.
- One camera move per clip.
- End with a continuity note: last frame, what the next scene must match, what is still unsaid.

## Scene block

```
SCENE N — title
0:00–0:08 of this clip. Place in the full short: …
Purpose:
Method: A or B
Attach:
Camera: start → end
Line: "..."

VIDEO PROMPT
...
```

Write the script to `__reference/` as markdown. Then stop and ask if they want Flow generation.

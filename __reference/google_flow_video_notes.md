# Google Flow + coding agent

Video: [Google Flow Now Connects to Claude Code](https://www.youtube.com/watch?v=AKcjBPvF788)
Channel: Srijan Builds
Watched via auto-captions on 21 Oct 2026. The captions mishear “Flow” as “Flux” and “Higgsfield” as “Hix Field”. The title and the steps are about Google Flow.

## What the video actually shows

A Chrome extension, searched in the video as a Flow connector, drives a logged-in Google Flow tab from a coding agent (Claude Code, or Antigravity as the free agent). It is not an official Google API.

The demo at the start is a Vox-style documentary made from about 50 still images and an edit. No video model and no video credits were used for that sample. Image generation inside Flow is described as the cheap or free part. Video, reference-to-video, and frame-to-video are the paid or credit-using part.

## The three setup steps in the video

1. Install the connector extension in Chrome, allow its permissions, and open its side panel.
2. Copy the extension’s setup prompt into the coding agent.
3. Click Arrange, and keep the Google Flow browser tab visible. On the free extension mode the side panel must also stay open. The video then sells a “Pro” plan, shown as about $1, which is claimed to be faster and to allow closing the side panel. The Flow tab must still stay visible.

## What this does not give this project

- No official Flow API key exists. Google’s programmable video path is the Gemini API: [video generation](https://ai.google.dev/gemini-api/docs/video).
- Veo 3.1 preview models in that API are scheduled to shut down on 22 Oct 2026. New work should use Gemini Omni Flash (`gemini-omni-1.1-flash`), not the preview Veo IDs.
- Flow’s own models and limits are listed by Google here: [Flow models](https://support.google.com/labs/answer/16352836). Clips are short (about 4, 6, or 8 seconds). A Short is several clips joined later.
- A third-party extension that needs every Chrome permission, a visible logged-in tab, and a separate paid plan is a browser remote-control, not a key I can store in `.env`.

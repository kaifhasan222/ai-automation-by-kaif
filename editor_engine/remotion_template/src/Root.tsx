import React from "react";
import { Composition, staticFile } from "remotion";
import { AnimatedReel } from "./AnimatedReel";
import { GeminiReel } from "./GeminiReel";
import type { AnimatedProps } from "./animatedTypes";
import type { ReelProps } from "./types";

const ANIMATED_DEFAULT: AnimatedProps = {
  title: "MCP in 30 sec",
  brand: "AI Kaif",
  whooshAudio: "sfx/whoosh.mp3",
  popAudio: "sfx/pop.mp3",
  bgmAudio: "sfx/bgm.mp3",
  scenes: [
    { kind: "hook", startSec: 0, endSec: 4, headline: "AI ko apps se kaun jodta hai?", emoji: "🤔" },
    { kind: "point", startSec: 4, endSec: 9, headline: "Har tool ka alag plug?", sub: "Chatbot ke paas tumhara data nahi hota", emoji: "🔌" },
    { kind: "diagram", startSec: 9, endSec: 16, headline: "MCP = USB-C", sub: "Host → Client → Server" },
    { kind: "meme", startSec: 16, endSec: 21, headline: "Bhai yeh toh ek port tha", sub: "10 alag integrations ki jagah", emoji: "😂" },
    { kind: "cta", startSec: 21, endSec: 25, headline: "Roz ek tech short", sub: "Follow AI Kaif", emoji: "🔥" },
  ],
};

const DEFAULT_PROPS: ReelProps = {
  faceVideo: "input/face.mp4",
  voiceAudio: "input/voice.mp3",
  whooshAudio: "sfx/whoosh.mp3",
  popAudio: "sfx/pop.mp3",
  bgmAudio: "sfx/bgm.mp3",
  hookText: "Yeh hai Future! 🔥",
  brand: "AI Kaif",
  words: [
    { text: "Yeh", startMs: 0, endMs: 280 },
    { text: "hai", startMs: 280, endMs: 480, highlight: true },
    { text: "Future!", startMs: 480, endMs: 900, highlight: true },
    { text: "AI", startMs: 1000, endMs: 1300, highlight: true },
    { text: "tools", startMs: 1300, endMs: 1700 },
    { text: "se", startMs: 1700, endMs: 1950 },
    { text: "kaam", startMs: 1950, endMs: 2300 },
    { text: "fast", startMs: 2300, endMs: 2700, highlight: true },
  ],
};

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="GeminiReel"
        component={GeminiReel}
        durationInFrames={300}
        fps={30}
        width={1080}
        height={1920}
        defaultProps={DEFAULT_PROPS}
        calculateMetadata={async ({ props }) => {
          // Duration from last caption word (+ padding), min 5s max 60s
          const last = props.words?.[props.words.length - 1]?.endMs ?? 5000;
          const seconds = Math.min(60, Math.max(5, last / 1000 + 0.6));
          return {
            durationInFrames: Math.round(seconds * 30),
            props,
          };
        }}
      />
      {/* Studio-friendly lower-res for faster iteration */}
      <Composition
        id="GeminiReelPreview"
        component={GeminiReel}
        durationInFrames={300}
        fps={30}
        width={720}
        height={1280}
        defaultProps={DEFAULT_PROPS}
        calculateMetadata={async ({ props }) => {
          const last = props.words?.[props.words.length - 1]?.endMs ?? 5000;
          const seconds = Math.min(60, Math.max(5, last / 1000 + 0.6));
          return {
            durationInFrames: Math.round(seconds * 30),
            props,
          };
        }}
      />
      <Composition
        id="AnimatedReel"
        component={AnimatedReel}
        fps={30}
        width={720}
        height={1280}
        defaultProps={ANIMATED_DEFAULT}
        durationInFrames={750}
        calculateMetadata={async ({ props }) => {
          const last = props.scenes?.[props.scenes.length - 1]?.endSec ?? 12;
          const seconds = Math.min(45, Math.max(8, last));
          return { durationInFrames: Math.round(seconds * 30), props };
        }}
      />
    </>
  );
};

// Keep staticFile referenced so bundler knows public assets exist in docs
void staticFile;

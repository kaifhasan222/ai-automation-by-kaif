import React, { useMemo } from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import type { CaptionWord } from "../types";

const CHUNK = 4;

function chunkWords(words: CaptionWord[]): CaptionWord[][] {
  const chunks: CaptionWord[][] = [];
  for (let i = 0; i < words.length; i += CHUNK) {
    chunks.push(words.slice(i, i + CHUNK));
  }
  return chunks;
}

/** Hormozi-style word captions with yellow highlights. */
export const Captions: React.FC<{ words: CaptionWord[] }> = ({ words }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const nowMs = (frame / fps) * 1000;

  const chunks = useMemo(() => chunkWords(words), [words]);
  const activeChunk =
    chunks.find((c) => {
      const start = c[0]?.startMs ?? 0;
      const end = c[c.length - 1]?.endMs ?? 0;
      return nowMs >= start && nowMs <= end + 120;
    }) ?? null;

  if (!activeChunk || activeChunk.length === 0) {
    return null;
  }

  const appear = spring({
    frame: Math.max(
      0,
      frame - Math.round(((activeChunk[0].startMs / 1000) * fps) || 0),
    ),
    fps,
    config: { damping: 200, stiffness: 200 },
  });
  const scale = interpolate(appear, [0, 1], [0.85, 1]);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: "18%",
        paddingLeft: 36,
        paddingRight: 36,
      }}
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: 10,
          transform: `scale(${scale})`,
          maxWidth: "92%",
        }}
      >
        {activeChunk.map((w, i) => {
          const on = nowMs >= w.startMs && nowMs <= w.endMs;
          const highlight = Boolean(w.highlight) || on;
          return (
            <span
              key={`${w.startMs}-${i}`}
              style={{
                fontFamily: 'Arial Black, "Helvetica Neue", Helvetica, sans-serif',
                fontSize: 64,
                lineHeight: 1.1,
                fontWeight: 900,
                color: highlight ? "#FFE566" : "#FFFFFF",
                WebkitTextStroke: "6px #000000",
                paintOrder: "stroke fill",
                textShadow: "0 6px 0 rgba(0,0,0,0.85)",
                transform: on ? "translateY(-4px) scale(1.06)" : "none",
                transition: "none",
              }}
            >
              {w.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

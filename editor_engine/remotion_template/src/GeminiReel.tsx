import React from "react";
import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Captions } from "./components/Captions";
import { FloatingIcons } from "./components/FloatingIcons";
import { MotionBg } from "./components/MotionBg";
import type { ReelProps } from "./types";

const HookBadge: React.FC<{ text: string }> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 14 } });
  const opacity = interpolate(frame, [0, 8, 55, 70], [0, 1, 1, 0], {
    extrapolateRight: "clamp",
  });
  if (!text) return null;
  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-start",
        alignItems: "center",
        paddingTop: "12%",
        opacity,
      }}
    >
      <div
        style={{
          transform: `scale(${interpolate(enter, [0, 1], [0.7, 1])})`,
          fontFamily: 'Arial Black, "Helvetica Neue", sans-serif',
          fontSize: 58,
          fontWeight: 900,
          color: "#FFE566",
          WebkitTextStroke: "5px #000",
          paintOrder: "stroke fill",
          textAlign: "center",
          padding: "10px 22px",
          maxWidth: "88%",
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};

export const GeminiReel: React.FC<ReelProps> = ({
  faceVideo,
  voiceAudio,
  bgmAudio,
  whooshAudio,
  popAudio,
  words,
  hookText,
  brand = "AI Kaif",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const faceSrc = faceVideo.startsWith("http") || faceVideo.startsWith("/")
    ? faceVideo
    : staticFile(faceVideo);
  const voiceSrc = voiceAudio.startsWith("/") ? voiceAudio : staticFile(voiceAudio);

  // Subtle Ken Burns zoom on face
  const zoom = interpolate(frame, [0, durationInFrames], [1.0, 1.08], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#050814" }}>
      <MotionBg intensity={0.5} />

      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          transform: `scale(${zoom})`,
        }}
      >
        <OffthreadVideo
          src={faceSrc}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
          muted
        />
      </AbsoluteFill>

      {/* Soft vignette so captions pop */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to top, rgba(0,0,0,0.75) 0%, transparent 38%, transparent 70%, rgba(0,0,0,0.35) 100%)",
        }}
      />

      <FloatingIcons />
      {hookText ? <HookBadge text={hookText} /> : null}
      <Captions words={words} />

      {/* Brand chip */}
      <div
        style={{
          position: "absolute",
          right: 28,
          bottom: 36,
          fontFamily: "Helvetica Neue, Arial, sans-serif",
          fontSize: 22,
          fontWeight: 700,
          color: "rgba(255,255,255,0.85)",
          background: "rgba(0,0,0,0.35)",
          padding: "8px 14px",
          borderRadius: 999,
          border: "1px solid rgba(255,255,255,0.2)",
        }}
      >
        {brand}
      </div>

      <Audio src={voiceSrc} />
      {bgmAudio ? (
        <Audio src={bgmAudio.startsWith("/") ? bgmAudio : staticFile(bgmAudio)} volume={0.18} />
      ) : null}
      {whooshAudio ? (
        <Sequence from={Math.round(0.2 * fps)} durationInFrames={Math.round(1.2 * fps)}>
          <Audio
            src={whooshAudio.startsWith("/") ? whooshAudio : staticFile(whooshAudio)}
            volume={0.55}
          />
        </Sequence>
      ) : null}
      {popAudio && words[0] ? (
        <Sequence
          from={Math.round((words[0].startMs / 1000) * fps)}
          durationInFrames={Math.round(0.5 * fps)}
        >
          <Audio
            src={popAudio.startsWith("/") ? popAudio : staticFile(popAudio)}
            volume={0.45}
          />
        </Sequence>
      ) : null}
    </AbsoluteFill>
  );
};

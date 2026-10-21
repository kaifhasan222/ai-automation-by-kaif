import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { MotionBg } from "./components/MotionBg";
import type { AnimatedProps, AnimatedScene } from "./animatedTypes";

const KIND_COLOR: Record<AnimatedScene["kind"], string> = {
  hook: "#FFE566",
  point: "#FFFFFF",
  diagram: "#7DF9FF",
  meme: "#FF5DA2",
  cta: "#B6FF6A",
};

const Card: React.FC<{ scene: AnimatedScene }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({ frame, fps, config: { damping: 14, stiffness: 120 } });
  const y = interpolate(enter, [0, 1], [80, 0]);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        padding: 48,
        transform: `translateY(${y}px) scale(${interpolate(enter, [0, 1], [0.86, 1])})`,
      }}
    >
      <div style={{ fontSize: 92, marginBottom: 12 }}>{scene.emoji || "✨"}</div>
      <div
        style={{
          fontFamily: "Arial Black, Helvetica, sans-serif",
          fontSize: scene.kind === "meme" ? 64 : 72,
          fontWeight: 900,
          color: KIND_COLOR[scene.kind],
          textAlign: "center",
          lineHeight: 1.05,
          WebkitTextStroke: "6px #000",
          paintOrder: "stroke fill",
          maxWidth: "92%",
        }}
      >
        {scene.headline}
      </div>
      {scene.sub ? (
        <div
          style={{
            marginTop: 28,
            fontFamily: "Helvetica Neue, Arial, sans-serif",
            fontSize: 36,
            fontWeight: 700,
            color: "#fff",
            textAlign: "center",
            maxWidth: "88%",
            background: "rgba(0,0,0,0.45)",
            padding: "14px 18px",
            borderRadius: 18,
          }}
        >
          {scene.sub}
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

const Diagram: React.FC<{ scene: AnimatedScene }> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const steps = (scene.sub || "Host → Client → Server").split("→").map((s) => s.trim());
  return (
    <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", padding: 40 }}>
      <div
        style={{
          fontFamily: "Arial Black, Helvetica, sans-serif",
          fontSize: 54,
          color: "#FFE566",
          WebkitTextStroke: "4px #000",
          paintOrder: "stroke fill",
          marginBottom: 36,
          textAlign: "center",
        }}
      >
        {scene.headline}
      </div>
      {steps.map((step, i) => {
        const local = Math.max(0, frame - i * 8);
        const pop = spring({ frame: local, fps, config: { damping: 12 } });
        return (
          <div key={step} style={{ opacity: pop, transform: `scale(${pop})`, marginBottom: 16 }}>
            <div
              style={{
                minWidth: 420,
                textAlign: "center",
                fontSize: 40,
                fontWeight: 800,
                color: "#041018",
                background: "#7DF9FF",
                borderRadius: 18,
                padding: "16px 22px",
              }}
            >
              {step}
            </div>
            {i < steps.length - 1 ? (
              <div style={{ textAlign: "center", fontSize: 36, color: "#fff" }}>↓</div>
            ) : null}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

export const AnimatedReel: React.FC<AnimatedProps> = ({
  scenes,
  brand = "AI Kaif",
  whooshAudio = "sfx/whoosh.mp3",
  popAudio = "sfx/pop.mp3",
  bgmAudio = "sfx/bgm.mp3",
  voiceAudio,
}) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ backgroundColor: "#070B16" }}>
      <MotionBg intensity={0.85} />
      {scenes.map((scene, index) => {
        const from = Math.round(scene.startSec * fps);
        const duration = Math.max(1, Math.round((scene.endSec - scene.startSec) * fps));
        return (
          <Sequence key={`${scene.kind}-${index}`} from={from} durationInFrames={duration}>
            {scene.kind === "diagram" ? <Diagram scene={scene} /> : <Card scene={scene} />}
            <Audio src={staticFile(index % 2 === 0 ? whooshAudio : popAudio)} volume={0.16} />
          </Sequence>
        );
      })}
      {voiceAudio ? <Audio src={staticFile(voiceAudio)} volume={1} /> : null}
      <Audio src={staticFile(bgmAudio)} volume={voiceAudio ? 0.06 : 0.16} />
      <div
        style={{
          position: "absolute",
          right: 28,
          bottom: 36,
          color: "#fff",
          fontWeight: 700,
          fontSize: 22,
          background: "rgba(0,0,0,0.35)",
          padding: "8px 14px",
          borderRadius: 999,
        }}
      >
        {brand}
      </div>
    </AbsoluteFill>
  );
};

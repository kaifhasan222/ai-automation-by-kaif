import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

/** Neon tech grid + drifting particles (Gemini-style atmosphere). */
export const MotionBg: React.FC<{ intensity?: number }> = ({ intensity = 0.55 }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;

  const waveY = interpolate(Math.sin(t * 1.4), [-1, 1], [height * 0.35, height * 0.55]);
  const glow = 0.25 + 0.15 * Math.sin(t * 2.2);

  const particles = Array.from({ length: 18 }, (_, i) => {
    const x = ((i * 97 + frame * (0.4 + (i % 5) * 0.08)) % (width + 40)) - 20;
    const y = (i * 73 + Math.sin(t + i) * 30) % height;
    const size = 3 + (i % 4);
    return { x, y, size, opacity: 0.15 + (i % 5) * 0.08 };
  });

  return (
    <AbsoluteFill style={{ opacity: intensity, pointerEvents: "none" }}>
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at 50% 30%, rgba(30,80,180,0.45) 0%, rgba(5,10,30,0.75) 55%, rgba(0,0,0,0.85) 100%)",
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage:
            "linear-gradient(rgba(0,200,255,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(0,200,255,0.08) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
          transform: `translateY(${(frame % 48) - 24}px)`,
          opacity: 0.35,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: "-10%",
          right: "-10%",
          top: waveY,
          height: 120,
          background:
            "linear-gradient(90deg, transparent, rgba(0,220,255,0.55), rgba(120,80,255,0.45), transparent)",
          filter: `blur(${8 + glow * 10}px)`,
          opacity: 0.55 + glow,
        }}
      />
      {particles.map((p, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: p.x,
            top: p.y,
            width: p.size,
            height: p.size,
            borderRadius: 2,
            background: "rgba(120, 220, 255, 0.9)",
            opacity: p.opacity,
            boxShadow: "0 0 8px rgba(0,200,255,0.8)",
          }}
        />
      ))}
    </AbsoluteFill>
  );
};

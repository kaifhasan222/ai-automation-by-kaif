import React from "react";
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

const ICONS = ["🚀", "⚡", "🤖", "✨", "🔥", "💡"];

export const FloatingIcons: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {ICONS.map((icon, i) => {
        const delay = i * 12;
        const local = Math.max(0, frame - delay);
        const enter = spring({
          frame: local,
          fps,
          config: { damping: 14, stiffness: 80 },
        });
        const x = (width * (0.08 + (i % 3) * 0.35) + Math.sin((frame + i * 20) / 18) * 18);
        const y =
          height * (0.12 + Math.floor(i / 3) * 0.18) +
          Math.cos((frame + i * 12) / 22) * 14;
        const opacity = interpolate(enter, [0, 1], [0, 0.55]);
        const scale = interpolate(enter, [0, 1], [0.4, 1]);

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x,
              top: y,
              fontSize: 42 + (i % 3) * 8,
              opacity,
              transform: `scale(${scale})`,
              filter: "drop-shadow(0 4px 10px rgba(0,0,0,0.45))",
            }}
          >
            {icon}
          </div>
        );
      })}
    </AbsoluteFill>
  );
};

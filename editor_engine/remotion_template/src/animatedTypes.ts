export type SceneKind = "hook" | "point" | "diagram" | "meme" | "cta";

export type AnimatedScene = {
  kind: SceneKind;
  startSec: number;
  endSec: number;
  headline: string;
  sub?: string;
  emoji?: string;
  line?: string;
};

export type AnimatedProps = {
  title: string;
  brand?: string;
  scenes: AnimatedScene[];
  whooshAudio?: string;
  popAudio?: string;
  bgmAudio?: string;
  voiceAudio?: string;
};

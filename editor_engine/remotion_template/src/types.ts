export type CaptionWord = {
  text: string;
  startMs: number;
  endMs: number;
  highlight?: boolean;
};

export type ReelProps = {
  faceVideo: string;
  voiceAudio: string;
  bgmAudio?: string;
  whooshAudio?: string;
  popAudio?: string;
  words: CaptionWord[];
  hookText?: string;
  brand?: string;
};

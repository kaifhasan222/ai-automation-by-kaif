"""HyperFrames HTML and Video Composer for Kaif AI Reels."""

from __future__ import annotations

import html
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from orchestrator.config import ROOT
from orchestrator.ffmpeg_utils import ffmpeg_exe
from orchestrator.media_source import ensure_sfx_library
from orchestrator.scene_generator import SceneClip

log = logging.getLogger("hyperframes_composer")


def build_hyperframes_html(
    *,
    clips: list[SceneClip],
    title: str = "AI Tech News",
    kicker: str = "NEW KAIF AI",
    out_html: Path,
) -> Path:
    """Generate deterministic HyperFrames HTML with GSAP animations, sound effects, and video clips."""
    total_duration = clips[-1].end_sec if clips else 10.0
    sfx = ensure_sfx_library()

    # Video clips markup
    video_elements = []
    card_elements = []
    audio_elements = []
    gsap_timelines = []

    # Copy / symlink assets relative to html parent
    target_dir = out_html.parent
    assets_dir = target_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Copy SFX to assets dir
    import shutil
    shutil.copy(sfx["whoosh"], assets_dir / "whoosh.mp3")
    shutil.copy(sfx["pop"], assets_dir / "pop.mp3")
    shutil.copy(sfx["bgm"], assets_dir / "bgm.mp3")

    for i, clip in enumerate(clips):
        # Copy scene video
        clip_rel_name = f"scene_{clip.index:02d}.mp4"
        shutil.copy(clip.video_path, assets_dir / clip_rel_name)

        # Video DOM
        vid_id = f"v_{clip.index}"
        zoom_id = f"z_{clip.index}"
        video_elements.append(
            f'      <div id="{zoom_id}" class="zoom clip" data-start="{clip.start_sec}" data-duration="{clip.duration}">\n'
            f'        <video id="{vid_id}" src="assets/{clip_rel_name}" playsinline data-has-audio="true" data-volume="1"></video>\n'
            f'      </div>'
        )

        # Bottom Card / Text DOM
        card_id = f"card_{clip.index}"
        card_elements.append(
            f'      <div id="{card_id}" class="card clip" data-start="{clip.start_sec}" data-duration="{clip.duration}">\n'
            f'        <div class="card-in">{html.escape(clip.headline)}'
            f'<span>{html.escape(clip.sub)}</span>' if clip.sub else ''
            f'</div>\n'
            f'      </div>'
        )

        # SFX DOM
        w_id = f"w_{clip.index}"
        audio_elements.append(
            f'      <audio id="{w_id}" class="clip" src="assets/whoosh.mp3" data-start="{clip.start_sec}" data-duration="0.5" data-volume="0.35"></audio>'
        )

        # GSAP Animation chunk for this card
        gsap_timelines.append(
            f'      tl.fromTo("#{card_id}", {{ y: 60, opacity: 0, scale: 0.92 }}, {{ y: 0, opacity: 1, scale: 1, duration: 0.45, ease: "back.out(1.6)" }}, {clip.start_sec});'
        )
        gsap_timelines.append(
            f'      tl.to("#{card_id}", {{ opacity: 0, duration: 0.25 }}, {clip.end_sec - 0.25});'
        )

    # Background music
    audio_elements.append(
        f'      <audio id="bgm" class="clip" src="assets/bgm.mp3" data-start="0" data-duration="{total_duration}" data-volume="0.12"></audio>'
    )

    videos_html = "\n".join(video_elements)
    cards_html = "\n".join(card_elements)
    audios_html = "\n".join(audio_elements)
    gsap_script = "\n".join(gsap_timelines)

    html_content = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=720, height=1280" />
    <title>{html.escape(title)}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@600;800&display=swap" rel="stylesheet" />
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{
        margin: 0;
        width: 720px;
        height: 1280px;
        overflow: hidden;
        background: #080b12;
      }}
      #root {{
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
        background: #080b12;
      }}
      .mesh-bg {{
        position: absolute;
        inset: 0;
        overflow: hidden;
        background: #080b12;
        z-index: 0;
      }}
      .mesh {{
        position: absolute;
        inset: -25%;
        filter: blur(48px);
        opacity: 0.85;
        background:
          radial-gradient(circle at 20% 30%, #3b82f6 0 16%, transparent 35%),
          radial-gradient(circle at 80% 50%, #8b5cf6 0 18%, transparent 35%),
          radial-gradient(circle at 50% 80%, #06b6d4 0 16%, transparent 35%);
      }}
      .kicker {{
        position: absolute;
        top: 36px;
        left: 0;
        width: 100%;
        text-align: center;
        z-index: 10;
        font-family: 'Inter', sans-serif;
        font-weight: 800;
        font-size: 19px;
        letter-spacing: 0.28em;
        color: #f5f5f7;
        text-shadow: 0 2px 10px rgba(0,0,0,0.6);
      }}
      .zoom {{
        position: absolute;
        left: 28px;
        top: 84px;
        width: 664px;
        height: 770px;
        border-radius: 36px;
        overflow: hidden;
        z-index: 2;
        border: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 24px 60px rgba(0,0,0,0.65);
      }}
      .zoom video {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        object-position: center 20%;
      }}
      .card {{
        position: absolute;
        left: 36px;
        right: 36px;
        top: 890px;
        z-index: 8;
        border-radius: 28px;
        padding: 24px 20px;
        background: rgba(15, 23, 42, 0.88);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.18);
        text-align: center;
        box-shadow: 0 16px 40px rgba(0,0,0,0.5);
      }}
      .card-in {{
        font-family: 'Anton', sans-serif;
        font-size: 50px;
        line-height: 1.05;
        letter-spacing: 0.03em;
        color: #ffffff;
        text-transform: uppercase;
      }}
      .card-in span {{
        display: block;
        color: #38bdf8;
        font-size: 38px;
        margin-top: 8px;
        letter-spacing: 0.02em;
      }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total_duration}" data-width="720" data-height="1280">
      <div class="mesh-bg"><div class="mesh" id="mesh"></div></div>
      <div class="kicker">{html.escape(kicker)}</div>

{videos_html}

{cards_html}

{audios_html}
    </div>

    <script>
      const tl = gsap.timeline({{ paused: true }});
      tl.fromTo("#mesh", {{
        "--hf-x1": "20%", "--hf-y1": "30%", "--hf-x2": "80%", "--hf-y2": "50%"
      }}, {{
        "--hf-x1": "70%", "--hf-y1": "60%", "--hf-x2": "30%", "--hf-y2": "40%",
        duration: {total_duration}, ease: "none"
      }}, 0);

{gsap_script}

      // Auto-play when opened directly in browser preview
      window.addEventListener("DOMContentLoaded", () => {{
        tl.play();
        document.querySelectorAll("video").forEach(v => v.play().catch(() => {{}}));
      }});
    </script>
  </body>
</html>
"""
    out_html.write_text(html_content, encoding="utf-8")
    log.info("HyperFrames HTML built at: %s", out_html)
    return out_html


def render_hyperframes_mp4(
    *,
    clips: list[SceneClip],
    output_mp4: Path,
    title: str = "Kaif AI Reel",
) -> Path:
    """Concatenate and render scene clips into a single high-quality 9:16 deliverable MP4."""
    ff = ffmpeg_exe()
    output_mp4.parent.mkdir(parents=True, exist_ok=True)
    concat_txt = output_mp4.parent / "concat_list.txt"

    lines = []
    for clip in clips:
        # absolute forward slash path for ffmpeg concat
        p_str = str(clip.video_path.resolve()).replace("\\", "/")
        lines.append(f"file '{p_str}'")

    concat_txt.write_text("\n".join(lines), encoding="utf-8")

    # Mux clips smoothly with x264
    cmd = [
        ff,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_txt),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(output_mp4),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        log.error("Render MP4 failed: %s", proc.stderr[-800:])
        raise RuntimeError(f"Render failed: {proc.stderr[-400:]}")

    log.info("Rendered deliverable video: %s (size: %s bytes)", output_mp4, output_mp4.stat().st_size)
    return output_mp4

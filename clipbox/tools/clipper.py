#!/usr/bin/env python3
"""ClipBox clipper: turn a session's markers into clips with ffmpeg.

Runs on your laptop (Python 3.9+, ffmpeg on PATH). Captions need: pip install faster-whisper

Examples
  # Cut audio clips from the box's own recording
  python tools/clipper.py sessions/2026-11-20_19-30-05

  # Cut clips from your camera file. --offset = seconds into the video where the
  # first of the two REC start beeps begins (find it in any editor or Audacity).
  python tools/clipper.py sessions/2026-11-20_19-30-05 --video cam.mp4 --offset 12.4

  # Vertical 9:16 with burned-in Hindi captions
  python tools/clipper.py SESSION --video cam.mp4 --offset 12.4 --vertical --captions --language hi

  # No camera? Make a vertical audiogram (waveform + captions) from audio.wav
  python tools/clipper.py SESSION --audiogram --captions
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Sequence

VIDEO_ARGS = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
AUDIO_ARGS = ["-c:a", "aac", "-b:a", "192k"]


# ---------------------------------------------------------------------------
# Planning (pure functions, easy to test)
# ---------------------------------------------------------------------------


@dataclass
class Clip:
    index: int
    marker_ids: List[int]
    start: float  # seconds in the source media
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def load_markers(session: Path) -> dict:
    session = Path(session)
    path = session if session.is_file() else session / "markers.json"
    if not path.exists():
        raise SystemExit(f"No markers.json found at {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["_folder"] = str(path.parent)
    return data


def plan_clips(
    markers: Sequence[dict],
    offset: float,
    pre: Optional[float] = None,
    post: Optional[float] = None,
    merge: bool = True,
    media_duration: Optional[float] = None,
) -> List[Clip]:
    """Map markers (t = seconds after the start beep) to clip windows in the source media.

    media time = offset + t. pre/post override the per-marker values when given.
    Overlapping windows are merged into one clip unless merge=False.
    """
    windows = []
    for m in sorted(markers, key=lambda m: float(m["t"])):
        t = offset + float(m["t"])
        p = float(m.get("pre", 20.0)) if pre is None else pre
        q = float(m.get("post", 10.0)) if post is None else post
        start, end = max(0.0, t - p), t + q
        if media_duration is not None:
            if start >= media_duration:
                print(f"  ! marker {m['id']} at {t:.1f}s is past the end of the media ({media_duration:.1f}s); "
                      f"check --offset", file=sys.stderr)
                continue
            end = min(end, media_duration)
        windows.append([start, end, [int(m["id"])]])

    if merge:
        merged: list = []
        for w in windows:
            if merged and w[0] <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], w[1])
                merged[-1][2].extend(w[2])
            else:
                merged.append(w)
        windows = merged

    return [Clip(index=i + 1, marker_ids=w[2], start=w[0], end=w[1]) for i, w in enumerate(windows)]


def clip_name(clip: Clip, ext: str) -> str:
    total = int(clip.start)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    stamp = f"{h}h{m:02d}m{s:02d}s" if h else f"{m:02d}m{s:02d}s"
    return f"clip_{clip.index:02d}_{stamp}.{ext}"


# ---------------------------------------------------------------------------
# Captions
# ---------------------------------------------------------------------------


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Cue:
    start: float
    end: float
    words: List[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(w.strip() for w in self.words if w.strip())


def group_words(words: Sequence[Word], max_words: int = 5, max_duration: float = 3.0, max_gap: float = 0.8) -> List[Cue]:
    """Short caption cues for vertical video: a few words at a time."""
    cues: List[Cue] = []
    for w in words:
        if not w.text.strip():
            continue
        cur = cues[-1] if cues else None
        if (
            cur is None
            or len(cur.words) >= max_words
            or w.end - cur.start > max_duration
            or w.start - cur.end > max_gap
        ):
            cues.append(Cue(start=w.start, end=w.end, words=[w.text]))
        else:
            cur.words.append(w.text)
            cur.end = w.end
    return cues


def srt_time(seconds: float) -> str:
    ms = int(round(max(0.0, seconds) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(cues: Sequence[Cue]) -> str:
    blocks = []
    for i, c in enumerate(cues, 1):
        end = max(c.end, c.start + 0.3)
        blocks.append(f"{i}\n{srt_time(c.start)} --> {srt_time(end)}\n{c.text}\n")
    return "\n".join(blocks)


class WhisperTranscriber:
    """Word-level transcription with faster-whisper, loaded once and reused for every clip."""

    def __init__(self, model: str = "small", language: Optional[str] = None):
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError:
            raise SystemExit("Captions need faster-whisper: pip install faster-whisper")
        print(f"Loading Whisper model '{model}' (first run downloads it)...")
        self.model = WhisperModel(model, device="cpu", compute_type="int8")
        self.language = language

    def __call__(self, wav_path: Path) -> List[Word]:
        segments, _info = self.model.transcribe(
            str(wav_path), language=self.language, word_timestamps=True, vad_filter=True
        )
        words: List[Word] = []
        for seg in segments:
            for w in seg.words or []:
                words.append(Word(start=float(w.start), end=float(w.end), text=w.word))
        return words


# ---------------------------------------------------------------------------
# ffmpeg
# ---------------------------------------------------------------------------


def require_ffmpeg() -> None:
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found. Install it (macOS: brew install ffmpeg, Ubuntu: sudo apt install ffmpeg, "
                         "Windows: winget install ffmpeg) and try again.")


def probe(path: Path) -> dict:
    """Duration and whether the file has video, using ffprobe (empty dict if unavailable)."""
    if not shutil.which("ffprobe"):
        return {}
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        return {}
    data = json.loads(out.stdout or "{}")
    info = {"has_video": any(s.get("codec_type") == "video" for s in data.get("streams", []))}
    try:
        info["duration"] = float(data["format"]["duration"])
    except (KeyError, TypeError, ValueError):
        pass
    return info


def vertical_filter(crop_x: float = 0.5) -> str:
    """Crop the widest 9:16 window (positioned by crop_x, 0=left 1=right) and scale to 1080x1920."""
    crop_x = min(1.0, max(0.0, crop_x))
    return (
        "crop=w='trunc(min(iw,ih*9/16)/2)*2':h='trunc(min(ih,iw*16/9)/2)*2'"
        f":x='(iw-ow)*{crop_x:.3f}':y='(ih-oh)/2',scale=1080:1920,setsar=1"
    )


def subtitle_filter(srt_name: str, vertical: bool, font: Optional[str]) -> str:
    # Sizes are in libass units (the video height is mapped to 288).
    style = ["FontSize=13" if vertical else "FontSize=16", "PrimaryColour=&H00FFFFFF", "OutlineColour=&H00000000",
             "BorderStyle=1", "Outline=2", "Shadow=0", "Bold=1", "Alignment=2",
             "MarginV=70" if vertical else "MarginV=20"]
    if font:
        style.insert(0, f"FontName={font}")
    return f"subtitles=filename='{srt_name}':force_style='{','.join(style)}'"


def build_command(
    source: Path,
    clip: Clip,
    out: Path,
    kind: str,
    vertical: bool = False,
    crop_x: float = 0.5,
    srt_name: Optional[str] = None,
    font: Optional[str] = None,
) -> List[str]:
    """ffmpeg command for one clip. kind: 'video', 'audio' or 'audiogram'."""
    ss, dur = f"{clip.start:.3f}", f"{clip.duration:.3f}"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    subs = subtitle_filter(srt_name, vertical or kind == "audiogram", font) if srt_name else None

    if kind == "audio":
        return cmd + ["-ss", ss, "-i", str(source), "-t", dur, "-vn", *AUDIO_ARGS, str(out)]

    if kind == "audiogram":
        graph = ("color=c=0x111111:s=1080x1920:r=30[bg];"
                 "[0:a]showwaves=s=1080x360:mode=cline:colors=white:rate=30[wave];"
                 "[bg][wave]overlay=0:780:shortest=1")
        graph += f",{subs}[v]" if subs else "[v]"
        return cmd + ["-ss", ss, "-t", dur, "-i", str(source), "-filter_complex", graph,
                      "-map", "[v]", "-map", "0:a", *VIDEO_ARGS, *AUDIO_ARGS, "-shortest",
                      "-movflags", "+faststart", str(out)]

    filters = []
    if vertical:
        filters.append(vertical_filter(crop_x))
    if subs:
        filters.append(subs)
    cmd += ["-ss", ss, "-i", str(source), "-t", dur]
    if filters:
        cmd += ["-vf", ",".join(filters)]
    return cmd + [*VIDEO_ARGS, *AUDIO_ARGS, "-movflags", "+faststart", str(out)]


def extract_wav(source: Path, clip: Clip, dest: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{clip.start:.3f}", "-i", str(source),
         "-t", f"{clip.duration:.3f}", "-vn", "-ac", "1", "-ar", "16000", str(dest)],
        check=True,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Turn ClipBox markers into clips.",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("session", type=Path, help="session folder (or its markers.json)")
    p.add_argument("--video", type=Path, help="camera/screen recording to cut instead of audio.wav")
    p.add_argument("--offset", type=float,
                   help="seconds into --video where the first REC start beep begins (required with --video)")
    p.add_argument("--out", type=Path, help="output folder (default: SESSION/clips)")
    p.add_argument("--pre", type=float, help="seconds before each press (default: value saved with the marker)")
    p.add_argument("--post", type=float, help="seconds after each press (default: value saved with the marker)")
    p.add_argument("--no-merge", action="store_true", help="keep overlapping clips separate")
    p.add_argument("--only", help="comma-separated clip numbers to render, e.g. 1,3")
    p.add_argument("--vertical", action="store_true", help="9:16 crop at 1080x1920 for Reels/Shorts")
    p.add_argument("--crop-x", type=float, default=0.5, help="horizontal crop position 0..1 (0.5 = centre)")
    p.add_argument("--audiogram", action="store_true", help="audio source only: render a 9:16 waveform video")
    p.add_argument("--captions", action="store_true", help="transcribe and burn in captions (needs faster-whisper)")
    p.add_argument("--language", help="caption language code, e.g. hi or en (default: auto-detect)")
    p.add_argument("--model", default="small", help="Whisper model: tiny, base, small, medium, large-v3")
    p.add_argument("--words", type=int, default=5, help="max words per caption line")
    p.add_argument("--font", help="caption font name (for Devanagari try 'Noto Sans Devanagari')")
    p.add_argument("--dry-run", action="store_true", help="print the plan and ffmpeg commands without running them")
    args = p.parse_args(argv)
    if args.video and args.offset is None:
        p.error("--offset is required with --video: the time (s) in your video where the first start beep "
                "begins. Open the video in any editor or Audacity and look for the two beeps.")
    if args.audiogram and args.video:
        p.error("--audiogram is for audio-only sessions; drop --video")
    return args


def run(argv: Optional[Sequence[str]] = None, transcriber_factory: Optional[Callable] = None) -> List[Path]:
    args = parse_args(argv)
    data = load_markers(args.session)
    folder = Path(data["_folder"])
    markers = data.get("markers", [])
    if not markers:
        print("This session has no markers. Nothing to clip.")
        return []

    if args.video:
        source, offset = args.video, float(args.offset)
    else:
        if not data.get("audio_file"):
            raise SystemExit("This session was recorded in marker-only mode (no audio.wav). "
                             "Pass your camera file with --video and --offset.")
        source = folder / data["audio_file"]
        if not source.exists():
            raise SystemExit(f"{source} not found. Copy the whole session folder from the board.")
        offset = float(data.get("audio_offset") or 0.0)

    if not args.dry_run:
        require_ffmpeg()
    info = probe(source) if not args.dry_run else {}
    kind = "video" if args.video else ("audiogram" if args.audiogram else "audio")
    if kind == "video" and info and not info.get("has_video", True):
        kind = "audiogram" if args.vertical else "audio"
        print(f"{source.name} has no video stream; making {kind} clips instead.")
    if kind == "audio" and args.vertical:
        kind = "audiogram"
    if kind == "audio" and args.captions:
        print("Captions need a video: making audiogram clips (add --vertical/--audiogram to silence this).")
        kind = "audiogram"

    clips = plan_clips(markers, offset, args.pre, args.post, merge=not args.no_merge,
                       media_duration=info.get("duration"))
    if args.only:
        wanted = {int(x) for x in args.only.split(",") if x.strip()}
        clips = [c for c in clips if c.index in wanted]

    out_dir = args.out or folder / "clips"
    ext = "m4a" if kind == "audio" else "mp4"
    print(f"Source: {source}  (marker t=0 at {offset:.2f}s)")
    print(f"{len(clips)} clip(s) -> {out_dir}  [{kind}{', vertical' if args.vertical else ''}"
          f"{', captions' if args.captions else ''}]")

    transcriber = None
    if args.captions and not args.dry_run:
        transcriber = (transcriber_factory or WhisperTranscriber)(args.model, args.language)

    written: List[Path] = []
    rows = []
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
    for clip in clips:
        out = out_dir / clip_name(clip, ext)
        ids = ",".join(str(i) for i in clip.marker_ids)
        print(f"  {clip.index:2d}. {clip.start:8.2f}s - {clip.end:8.2f}s  ({clip.duration:4.1f}s, marker {ids})"
              f"  {out.name}")
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            srt_name = None
            if args.captions:
                srt_name = "captions.srt"
                if not args.dry_run:
                    wav = tmpdir / "clip.wav"
                    extract_wav(source, clip, wav)
                    cues = group_words(transcriber(wav), max_words=args.words)
                    srt = to_srt(cues)
                    (tmpdir / srt_name).write_text(srt, encoding="utf-8")
                    out.with_suffix(".srt").write_text(srt, encoding="utf-8")
            cmd = build_command(source.resolve(), clip, out.resolve(), kind, vertical=args.vertical,
                                crop_x=args.crop_x, srt_name=srt_name, font=args.font)
            if args.dry_run:
                print("      " + " ".join(cmd))
                continue
            # Run inside tmpdir so the subtitles filter gets a plain relative filename (no path escaping).
            result = subprocess.run(cmd, cwd=tmpdir, capture_output=True, text=True)
            if result.returncode != 0:
                raise SystemExit(f"ffmpeg failed on clip {clip.index}:\n{result.stderr.strip()}")
        written.append(out)
        rows.append([clip.index, out.name, f"{clip.start:.3f}", f"{clip.end:.3f}", ids])

    if rows:
        with open(out_dir / "clips.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["clip", "file", "start_seconds", "end_seconds", "markers"])
            w.writerows(rows)
        print(f"Done: {len(written)} clip(s) in {out_dir}")
    return written


def main() -> None:
    try:
        run()
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()

"""FFmpeg video assembly (see VIDEO_ENGINE.md §7).

`paragraph_weights()` is transplanted from the legacy engine: slide durations are weighted by
the character length of the narration paragraph each slide represents, floored at a sensible
minimum per slide kind, then rescaled so the sum matches the narration audio's real duration
exactly (no drift, no silence padding).

New, additive-only features: brand intro/outro video splicing (concatenated around the
slideshow, each re-encoded onto a shared timebase so `concat` doesn't choke on mismatched
parameters) and burned-in captions generated from the same per-slide timing via an SRT file fed
through ffmpeg's `subtitles` filter (requires libass, bundled with most ffmpeg builds).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from .brand import BrandTheme, DEFAULT_BRAND
from .narration import probe_audio_duration

MIN_STATEMENT_SECONDS = 7.0
MIN_SHORT_SECONDS = 5.5


@dataclass
class SlideTiming:
    path: Path
    start: float
    duration: float
    text: str = ""


def paragraph_weights(texts: Sequence[str], total_duration: float, floors: Optional[Sequence[float]] = None) -> List[float]:
    """Character-length-weighted per-slide duration, floored per-slide, then rescaled to sum
    exactly to `total_duration`. `floors` lets callers give short slides (map/quote/close) a
    lower minimum than narration-heavy statement slides."""
    n = len(texts)
    if n == 0:
        return []
    if floors is None:
        floors = [MIN_STATEMENT_SECONDS] * n
    lengths = [max(1, len(t)) for t in texts]
    total_len = sum(lengths)
    raw = [total_duration * (length / total_len) for length in lengths]
    floored = [max(raw[i], floors[i]) for i in range(n)]

    floor_sum = sum(floored)
    if floor_sum <= 0:
        return [total_duration / n] * n
    scale = total_duration / floor_sum
    scaled = [d * scale for d in floored]

    # Rounding can leave the sum a few milliseconds off; correct the final slide.
    drift = total_duration - sum(scaled)
    scaled[-1] = max(0.5, scaled[-1] + drift)
    return scaled


def build_slide_timings(slide_paths: List[Path], slide_texts: List[str], slide_kinds: List[str], audio_duration: float) -> List[SlideTiming]:
    floors = [MIN_STATEMENT_SECONDS if kind == "statement" else MIN_SHORT_SECONDS for kind in slide_kinds]
    durations = paragraph_weights(slide_texts, audio_duration, floors=floors)
    timings: List[SlideTiming] = []
    cursor = 0.0
    for path, text, duration in zip(slide_paths, slide_texts, durations):
        timings.append(SlideTiming(path=path, start=cursor, duration=duration, text=text))
        cursor += duration
    return timings


def _format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


MAX_CAPTION_CHARS = 84
MIN_CAPTION_SECONDS = 0.9


def _split_caption_cues(text: str, max_chars: int = MAX_CAPTION_CHARS) -> List[str]:
    """Break a slide's full narration chunk into short, readable caption-sized pieces. A caption
    showing an entire multi-sentence paragraph at once word-wraps into a dozen+ lines that fill
    the whole frame — captions need to be a line or two, timed across the slide, not one giant
    cue for the slide's whole on-screen duration."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    cues: List[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            cues.append(current)
        if len(sentence) <= max_chars:
            current = sentence
        else:
            # A single sentence longer than the limit: split on word boundaries instead.
            words = sentence.split()
            current = ""
            for word in words:
                trial = f"{current} {word}".strip()
                if len(trial) <= max_chars:
                    current = trial
                else:
                    if current:
                        cues.append(current)
                    current = word
    if current:
        cues.append(current)
    return cues or [text.strip()]


def write_captions_srt(timings: List[SlideTiming], output_path: Path) -> Path:
    lines = []
    index = 1
    for timing in timings:
        if not timing.text.strip():
            continue
        cues = _split_caption_cues(timing.text)
        cue_durations = paragraph_weights(cues, timing.duration, floors=[MIN_CAPTION_SECONDS] * len(cues))
        cursor = timing.start
        for cue_text, cue_duration in zip(cues, cue_durations):
            lines.append(str(index))
            lines.append(f"{_format_srt_timestamp(cursor)} --> {_format_srt_timestamp(cursor + cue_duration)}")
            lines.append(cue_text)
            lines.append("")
            cursor += cue_duration
            index += 1
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _run(cmd: List[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg command failed: {' '.join(cmd)}\n{result.stderr[-4000:]}")


def _slideshow_concat_file(timings: List[SlideTiming], concat_path: Path) -> None:
    lines = []
    for timing in timings:
        lines.append(f"file '{timing.path.resolve()}'")
        lines.append(f"duration {timing.duration:.3f}")
    # ffmpeg's concat demuxer needs the last file repeated without a duration line.
    if timings:
        lines.append(f"file '{timings[-1].path.resolve()}'")
    concat_path.write_text("\n".join(lines), encoding="utf-8")


def assemble_video(
    slide_paths: List[Path],
    slide_texts: List[str],
    slide_kinds: List[str],
    narration_path: Path,
    output_path: Path,
    brand: Optional[BrandTheme] = None,
    work_dir: Optional[Path] = None,
) -> Path:
    """Assemble the slideshow + narration (+ optional intro/outro + captions) into a final mp4."""
    brand = brand or DEFAULT_BRAND
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is not installed or not on PATH.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    work_dir = work_dir or output_path.parent / f".{output_path.stem}_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    audio_duration = probe_audio_duration(narration_path)
    timings = build_slide_timings(slide_paths, slide_texts, slide_kinds, audio_duration)

    concat_path = work_dir / "slides_concat.txt"
    _slideshow_concat_file(timings, concat_path)

    slideshow_path = work_dir / "slideshow.mp4"
    vf_filters = [f"scale={brand.width}:{brand.height}", "format=yuv420p"]

    captions_path: Optional[Path] = None
    if brand.captions_enabled:
        captions_path = write_captions_srt(timings, work_dir / "captions.srt")
        position = "Alignment=2" if brand.caption_position == "bottom" else "Alignment=6"
        vf_filters.append(
            f"subtitles={captions_path}:force_style='FontSize={brand.caption_font_size},{position}'"
        )

    _run([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_path),
        "-i", str(narration_path),
        "-vf", ",".join(vf_filters),
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage",
        "-c:a", "aac", "-b:a", brand.audio_bitrate,
        "-r", str(brand.fps),
        "-shortest",
        str(slideshow_path),
    ])

    segments = []
    if brand.intro_video_path and Path(brand.intro_video_path).exists():
        segments.append(_normalize_segment(Path(brand.intro_video_path), work_dir / "intro_norm.mp4", brand))
    segments.append(slideshow_path)
    if brand.outro_video_path and Path(brand.outro_video_path).exists():
        segments.append(_normalize_segment(Path(brand.outro_video_path), work_dir / "outro_norm.mp4", brand))

    if len(segments) == 1:
        shutil.move(str(slideshow_path), str(output_path))
    else:
        _concat_with_filter(segments, output_path, brand)

    shutil.rmtree(work_dir, ignore_errors=True)
    return output_path


def _normalize_segment(src: Path, dest: Path, brand: BrandTheme) -> Path:
    """Re-encode an intro/outro clip onto the same resolution/fps/audio format as the
    slideshow, and synthesize a silent audio track if the clip has none, so `concat` filter
    graphs never hit a mismatched-stream error."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(src)],
        capture_output=True, text=True,
    )
    has_audio = bool(probe.stdout.strip())

    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if not has_audio:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    cmd += [
        "-vf", f"scale={brand.width}:{brand.height},format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", brand.audio_bitrate,
        "-r", str(brand.fps),
        "-shortest",
        str(dest),
    ]
    _run(cmd)
    return dest


def _concat_with_filter(segments: List[Path], output_path: Path, brand: BrandTheme) -> None:
    inputs: List[str] = []
    filter_parts: List[str] = []
    for i, seg in enumerate(segments):
        inputs += ["-i", str(seg)]
        filter_parts.append(f"[{i}:v:0][{i}:a:0]")
    filter_complex = "".join(filter_parts) + f"concat=n={len(segments)}:v=1:a=1[outv][outa]"
    _run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", brand.audio_bitrate,
        "-r", str(brand.fps),
        str(output_path),
    ])

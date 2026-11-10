"""ElevenLabs narration synthesis (see VIDEO_ENGINE.md §6).

The script text is sent to ElevenLabs verbatim — it is never rewritten or summarized by this
module. Voice resolution accepts either a raw ElevenLabs voice ID (looks like an opaque
20-character token) or a human-readable voice name (looked up via the list-voices endpoint).
Long scripts are split into chunks under ElevenLabs' per-request character limit and the
resulting audio files are concatenated with ffmpeg, so narration length is not bounded by any
single API call.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import List, Optional

import requests

ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"
MAX_CHUNK_CHARS = 2200
_VOICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{18,24}$")


class NarrationError(RuntimeError):
    pass


def _chunk_script(text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: List[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(paragraph) <= max_chars:
                current = paragraph
            else:
                # A single paragraph longer than the limit: split on sentence boundaries.
                sentences = re.split(r"(?<=[.!?])\s+", paragraph)
                current = ""
                for sentence in sentences:
                    trial = f"{current} {sentence}".strip()
                    if len(trial) <= max_chars:
                        current = trial
                    else:
                        if current:
                            chunks.append(current)
                        current = sentence
    if current:
        chunks.append(current)
    return chunks or [text]


def resolve_voice_id(voice_ref: str, api_key: str) -> str:
    """Accept either a literal ElevenLabs voice ID or a voice name to look up."""
    if _VOICE_ID_PATTERN.match(voice_ref):
        return voice_ref
    resp = requests.get(f"{ELEVENLABS_API_BASE}/voices", headers={"xi-api-key": api_key}, timeout=30)
    resp.raise_for_status()
    voices = resp.json().get("voices", [])
    for voice in voices:
        if voice.get("name", "").strip().lower() == voice_ref.strip().lower():
            return voice["voice_id"]
    raise NarrationError(f"No ElevenLabs voice found matching name or ID: {voice_ref!r}")


def _synthesize_chunk(text: str, voice_id: str, api_key: str, model_id: str) -> bytes:
    resp = requests.post(
        f"{ELEVENLABS_API_BASE}/text-to-speech/{voice_id}",
        headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        json={
            "text": text,
            "model_id": model_id,
            "voice_settings": {"stability": 0.45, "similarity_boost": 0.75, "style": 0.15, "use_speaker_boost": True},
        },
        timeout=120,
    )
    if resp.status_code != 200:
        raise NarrationError(f"ElevenLabs TTS request failed ({resp.status_code}): {resp.text[:500]}")
    return resp.content


def synthesize_narration(
    script_text: str,
    voice_ref: str,
    api_key: str,
    output_path: Path,
    model_id: str = "eleven_turbo_v2_5",
) -> Path:
    """Synthesize `script_text` (sent verbatim) with the resolved voice and write an mp3 to
    `output_path`. Long scripts are chunked and concatenated with ffmpeg."""
    if not api_key:
        raise NarrationError("ELEVENLABS_API_KEY is not configured.")
    if not script_text.strip():
        raise NarrationError("Lesson script is empty; nothing to narrate.")

    voice_id = resolve_voice_id(voice_ref, api_key)
    chunks = _chunk_script(script_text)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if len(chunks) == 1:
        audio = _synthesize_chunk(chunks[0], voice_id, api_key, model_id)
        output_path.write_bytes(audio)
        return output_path

    tmp_dir = output_path.parent / f".{output_path.stem}_chunks"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    chunk_paths: List[Path] = []
    try:
        for i, chunk in enumerate(chunks):
            audio = _synthesize_chunk(chunk, voice_id, api_key, model_id)
            chunk_path = tmp_dir / f"chunk_{i:03d}.mp3"
            chunk_path.write_bytes(audio)
            chunk_paths.append(chunk_path)

        concat_list = tmp_dir / "concat.txt"
        concat_list.write_text("\n".join(f"file '{p.resolve()}'" for p in chunk_paths), encoding="utf-8")
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(output_path)],
            check=True, capture_output=True,
        )
    finally:
        for p in chunk_paths:
            p.unlink(missing_ok=True)
        (tmp_dir / "concat.txt").unlink(missing_ok=True)
        try:
            tmp_dir.rmdir()
        except OSError:
            pass

    return output_path


def probe_audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(result.stdout.strip())

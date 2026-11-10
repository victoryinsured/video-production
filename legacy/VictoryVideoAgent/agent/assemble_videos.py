from pathlib import Path
import json
from pipeline import ensure_dirs, load_config, extract_scripts, render_slides, generate_narration, assemble_videos, MANIFESTS

if __name__ == "__main__":
    ensure_dirs()
    cfg = load_config()
    lessons = extract_scripts(cfg)
    slide_manifest = render_slides(cfg, lessons)
    audio_records = generate_narration(cfg, lessons)
    assemble_videos(cfg, slide_manifest, audio_records)

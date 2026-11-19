# Victory Engine

The Python rendering core of Victory Video Studio. This package is the preserved and extended
production engine from the original `VictoryVideoAgent_AllModules_Complete_v1_3_Windows` package
— see `/VIDEO_ENGINE.md` at the repo root for the full inspection this rewrite is built from, and
`/ARCHITECTURE.md` for how the Node web app calls into it.

It is **not** a long-running service. The Node job-queue worker invokes it as a short-lived CLI
subprocess, once per pipeline step, passing a JSON job file in and reading one JSON result off
stdout:

```bash
python -m victory_engine.cli job.json
```

See `victory_engine/cli.py` for the full list of supported `step` values and their job-file
shapes (`parse_document`, `render_slides`, `synthesize_narration`, `assemble_video`,
`build_editable_deck`, `moodle_description`).

## Setup

Use a virtualenv — some sandboxes/containers ship a system Python with a `cryptography` package
conflict between apt and pip installs that breaks `pypdf`'s crypto backend. A clean venv avoids
it entirely:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`ffmpeg` and `ffprobe` must be on `PATH` (used by `narration.py` for chunk concatenation and by
`video.py` for slideshow assembly). Caption burn-in additionally requires an ffmpeg build with
`libass` (`ffmpeg -filters | grep subtitles` to check).

## Running tests

```bash
.venv/bin/python -m pytest tests/ -q
```

## Module map

| Module | Responsibility |
| --- | --- |
| `brand.py` | `BrandTheme` dataclass; exact legacy palette as defaults; dict (de)serialization for brand templates coming from the web app. |
| `fonts.py` | Cross-platform font resolution; bundled Liberation Sans is the default, with an OS fallback chain kept for local dev convenience. |
| `text_utils.py` | Slugify, paragraph normalization, keyword extraction — transplanted verbatim from the legacy engine. |
| `readers.py` | DOCX/PDF/TXT/Markdown → flat paragraph list, normalized to one shape regardless of source format. |
| `parser.py` | The curriculum grammar: paragraphs → `ParsedCourse`/`ParsedModule`/`ParsedLesson`/`ParsedResource`. Strict superset of the legacy grammar. |
| `render.py` | Pillow slide rendering — the 7 legacy slide "kinds", exact palette, plus brand logo overlay. |
| `narration.py` | ElevenLabs TTS; script sent verbatim; chunking + ffmpeg concat for long scripts. |
| `video.py` | ffmpeg slideshow assembly; `paragraph_weights()` timing algorithm; intro/outro splicing; caption burn-in. |
| `editable_assets.py` | Editable PPTX export mirroring each slide's text content. |
| `moodle_text.py` | Lesson/module description HTML (consumed directly by the Node Moodle integration). |
| `tracker.py` | Lightweight JSON run log written alongside a lesson's output, independent of the Node job-queue DB. |
| `cli.py` | The subprocess entry point the Node worker calls. |

## What is preserved vs. new

See `/VIDEO_ENGINE.md` §15 for the full preserve/change table. In short: the palette, font
hierarchy intent, slide "kinds", content-selection heuristics, and `paragraph_weights()` timing
algorithm are preserved exactly. New, additive-only capabilities: PDF/Markdown readers,
`RESOURCE:` parsing, brand logo overlay, intro/outro splicing, burned-in captions, and a
persisted step-state model (owned by the Node layer, not this package).

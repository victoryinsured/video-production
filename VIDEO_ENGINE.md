# VIDEO_ENGINE.md — Inspection of the Existing Victory Video Production Agent

This document is the required "inspect before you touch anything" record. It describes
`VictoryVideoAgent_AllModules_Complete_v1_3_Windows.zip` (v1.3, dated 2026-06-08) exactly as
it worked before this migration, and identifies what is Windows-specific vs. portable. The
original package is preserved unmodified in [`legacy/VictoryVideoAgent/`](legacy/VictoryVideoAgent)
for reference and diffing; nothing in this document is speculative — every claim below is
traced to a specific file.

## 1. What the package is

A **single-user, one-module-at-a-time, local Windows tool**. You double-click a `.bat` file,
it activates one Word script out of a library of module scripts, and a ~1,400-line Python
script (`agent/pipeline.py`) runs seven steps end-to-end, writing everything to a fixed
`output/` folder next to the script. There is no server, no database, no UI beyond Command
Prompt output, and no concept of more than one course.

## 2. Entry points and launchers (Windows-specific)

| File | Role |
|---|---|
| `SETUP_WINDOWS.bat` | Finds `py -3.12`, creates `.venv`, `pip install -r requirements.txt`, copies `config.example.json` → `config.json` on first run. |
| `RUN_MODULE.bat` | Activates venv, runs `agent/select_module.py` (interactive prompt for module 2–15), then `agent/run_agent.py`. |
| `RUN_ME.bat` | Activates venv, runs `agent/run_agent.py` on whatever module is already active. |
| `agent/select_module.py` | Copies the chosen `module_scripts/victory-framework-moduleN-scripts.docx` into `input_scripts/` (clearing any previous active file first), extracts the module title from the docx's `MODULE:` line, and rewrites `config/config.json` + `CURRENT_MODULE.txt`. |

All three `.bat` files are pure orchestration (`cd /d "%~dp0"`, venv activate, `python ...`) —
none of the actual production logic lives in the batch files. That means **the Windows
dependency is shallow**: it's the launcher plumbing and the Windows font path, not the
rendering logic itself.

Windows-specific assumptions found in the Python code itself:
- `agent/pipeline.py::font_candidates()` looks first in `%WINDIR%/Fonts` (`arial.ttf`,
  `calibri.ttf`, bold variants) before falling through to Linux paths (Noto Sans / Liberation
  Sans, already present as fallbacks — this is why the engine ran at all when I inspected it
  here on Linux).
- `SETUP_WINDOWS.bat` pins Python 3.12 specifically to dodge a Python 3.15/`lxml` wheel build
  failure on Windows — not a cross-platform constraimport.
- The optional delivery step (`upload_to_drive`) copies to a **Google Drive for Desktop**
  sync folder — i.e. a local folder path, not the Drive API. This is a Windows/macOS desktop
  workflow, not a real integration.
- Every path is built from `ROOT = Path(__file__).resolve().parents[1]` and fixed relative
  folder names (`input_scripts`, `output/...`) — this is OS-agnostic pathlib, but it assumes
  **one single working tree per machine, one module active at a time**. That singleton-folder
  design (not the OS) is the thing that has to change for a concurrent, multi-course web app.

**Verdict:** nothing here needs a Windows OS to run. FFmpeg, Python, and Pillow all run
identically on Linux/macOS. The `.bat` launchers and the `%WINDIR%` font lookup are the only
literal Windows-isms, and both are trivially replaced (POSIX launcher scripts / cross-platform
font resolution with bundled fonts as the top priority — see §11).

## 3. Configuration (`config/config.json`, `config/config.example.json`)

One global JSON file, deep-merged onto `DEFAULT_CONFIG` in `pipeline.py`. Fields:

| Field | Meaning |
|---|---|
| `course_name` | Printed on every slide header and in trackers/Moodle text. Always "Victory Framework" in this package — there is no multi-course concept. |
| `module_number`, `module_name` | Set by `select_module.py`; drive lesson numbering (`{module}.{lesson}`), filenames, and slide headers. |
| `input_pattern` | Glob for the active script file, default `*.docx` (falls back to `*.txt`). |
| `overwrite_existing_audio` | Cost control — skip ElevenLabs calls for lessons whose MP3 already exists. |
| `overwrite_existing_videos` | Whether to re-render an MP4 that already exists. |
| `treat_lesson_headings_as_metadata` | If true (default), the `LESSON:` metadata line itself is not narrated. |
| `elevenlabs.*` | `enabled`, `api_key` (blank by convention), `api_key_env_var` (`ELEVENLABS_API_KEY`), `voice_id` (name or ID), `model_id`, `stability`, `similarity_boost`, `style`, `use_speaker_boost`, `max_chars_per_request`. |
| `video.*` | `width`, `height`, `fps`, `audio_bitrate` — all fixed at 1920×1080/30fps/192k in practice. |
| `delivery.*` | `copy_to_google_drive_sync_folder`, `google_drive_sync_folder` (a local path). |

There is exactly one config file for the whole machine — no per-course or per-brand config.
That's the other big thing the web version has to add (§ "Course Defaults" in the product
brief) without touching how these fields are actually *used* by the renderer.

## 4. Script / curriculum parsing (`extract_scripts`, `split_lessons_from_paragraphs`)

This is the part explicitly called out as "reuse and expand" — documented in full.

- **Input discovery** (`discover_input_files`): globs `input_scripts/` for the configured
  pattern, ignoring placeholder files named `PUT_*`. Falls back from `.docx` to `.txt`.
- **Paragraph extraction** (`read_docx_paragraphs` / `read_text_paragraphs`): python-docx for
  `.docx`; for `.txt`, blank-line-delimited paragraphs, with any line that matches a lesson
  heading forced to flush and start fresh even without a blank line before it.
- **Metadata-block format** (the format actually used by every bundled module script,
  confirmed by reading `input_scripts/victory-framework-module2-scripts.docx` directly):
  ```
  COURSE:  Victory Framework
  MODULE:  The Engine — Getting Answers to What You Don't Know
  LESSON:  The Skill That Beats Experience: Getting Answers You Were Never Given
  TYPE:  Video
  <narration paragraphs...>
  COURSE: ...
  MODULE: ...
  LESSON: <next lesson>
  TYPE: Video
  <narration paragraphs...>
  ```
  `detect_script_metadata()` matches `^(course|module|lesson|type):\s*(.+)$` case-insensitively.
  Every `LESSON:` line starts a new lesson block; `COURSE:`/`MODULE:`/`TYPE:` lines are consumed
  as metadata and **never narrated**. This is the primary format in production today.
- **Numbered-heading format** (fallback, `detect_lesson_heading()`): regexes for
  `Lesson 3.1: Title`, `Module 2 Lesson 3.1: Title`, or a bare `3.1: Title` line — used when a
  script isn't in the metadata-block style (e.g. plain `.txt` uploads).
- **Sequential numbering**: `extract_scripts()` renumbers every detected lesson as
  `{module_number}.{n}` (n = 1, 2, 3… in document order) unless the heading already contained a
  dot (`"3.1"`), which is kept as-is. So the *document order* of `LESSON:` blocks is what
  determines lesson number, not any number written in the script.
- **Narration is never rewritten.** The exact extracted paragraphs (joined with blank lines)
  are written verbatim to `output/scripts/{slug}.txt`. This file *is* the TTS input later —
  the "story rule" ("if the script says it, the voice reads it") is enforced structurally, not
  by convention.
- **What the current parser does NOT detect** (must be added, not replacing what exists):
  course-level description, resource blocks, explicit video/lesson descriptions, knowledge
  checks, or production instructions. Only `COURSE / MODULE / LESSON / TYPE` + narration body
  are recognized today. There is no `RESOURCE:` handling anywhere in the codebase.
- **Output manifest**: `output/manifests/lessons_manifest.json` — course, module, module_number,
  and the full lesson list with `lesson_number`, `lesson_title`, `lesson_slug`, `narration_file`,
  `word_count`, `paragraph_count`, `status`.

## 5. Slide generation (`render_slides`, `make_slide_specs`, `RENDERERS`)

Fully procedural — no template files, no external slide assets (confirmed: `templates/` only
contains a placeholder README). Everything is drawn with Pillow directly in `pipeline.py`.

- **Canvas**: 1920×1080 RGBA. `create_background()` builds one shared base — a maroon-to-black
  radial vignette, a faint 96px grid, a double border, and a translucent diagonal maroon wedge
  in the top-right — cached in `_BASE_BG` and copied per slide (cheap re-render).
- **Brand palette** (module-level constants, currently hardcoded, must become the *default*
  brand template rather than be deleted):
  `INK`, `MAROON_BLACK`, `MAROON_DEEP`, `MAROON`, `CREAM`, `PARCHMENT`, `WARM_GRAY`, `GOLD`,
  `GOLD_DARK`, `OFF_WHITE`, `CHARCOAL`, `BORDER` — all explicit RGB tuples at the top of the file.
- **Fonts**: two logical roles, `sans` and `sans_bold`, resolved by `font_candidates()`
  (Windows Arial/Calibri → Linux Noto Sans → Liberation Sans → URW Nimbus → PIL default bitmap
  font as last resort). No font files are bundled with the package.
- **Slide "kinds"** (`RENDERERS` dict) — seven distinct layouts, each a hand-drawn composition
  of title block, gold accent rule, and one or more `card()` panels (opaque cream rounded
  rectangles with a soft drop shadow, dark ink text — the README calls this out explicitly as
  the "cream-card contrast fix", i.e. a past bug where translucent cream + light text was
  unreadable in the exported MP4):
  1. `cover` — title/subtitle + right-side "VICTORY FRAMEWORK" feature card with 3 bullet lines
     and an anchor sentence.
  2. `statement` — title + up to 4 stacked "core idea" cards with a gold tick mark.
  3. `map` — title + up to 6 numbered keyword cards in a 3-column grid.
  4. `comparison` — title + Before/After two-column cards, gold vs. warm-gray accent bars.
  5. `flow` — title + up to 5 numbered step cards connected by gold arrows.
  6. `quote` — title + one large "KEY TRUTH" quote card.
  7. `close` — eyebrow + big title + optional subtitle card, no right-side art (lesson outro).
- **Content selection is algorithmic, not AI**: `make_slide_specs()` pulls straight from the
  extracted narration — first paragraph as the cover anchor, next 1–3 as "core idea" bullets,
  keyword-frequency extraction (`extract_keywords`, a stop-word-filtered word-frequency ranker,
  no ML) for the map/flow slides, a comparison split around the paragraph midpoint, and the
  second-to-last/last paragraphs for quote/close. Always produces up to 8 slides per lesson.
- Every slide gets a shared `header_footer()`: course name (uppercase) + module name top-left,
  a divider rule, a lesson-number/slide-count footer, a gold progress bar, and an eyebrow badge
  (opaque cream pill, dark maroon text — same contrast-fix logic).
- Slides are saved as `slide_NN.png` under `output/slides/{lesson_slug}/`, and a
  `slide_manifest.json` plus a human-readable Markdown storyboard
  (`output/moodle_descriptions/storyboards/{slug}_storyboard.md`, mapping each slide to the
  script paragraph numbers it visualizes) are written alongside.

**This rendered look — palette, card style, layout kinds, header/footer chrome — is the
reference design.** The web migration exposes these as configurable *inputs* (brand template
records) with these exact values as defaults; it does not redesign the layouts themselves
unless a course's brand template explicitly overrides a color/font/logo.

## 6. Narration (`generate_narration`, ElevenLabs integration)

- Disabled by default (`elevenlabs.enabled: false`) — the whole rest of the pipeline (scripts,
  slides, trackers, Moodle text, editable assets) runs for free without it, by design.
- API key resolution: env var named by `elevenlabs.api_key_env_var` (default
  `ELEVENLABS_API_KEY`) takes priority over `config.json`'s `api_key` field — i.e. the existing
  code already keeps the key out of the config file when set up correctly.
- Voice resolution (`resolve_voice_id`): if `voice_id` already looks like a raw ElevenLabs ID
  (`[A-Za-z0-9_-]{12,}`), use it directly; otherwise call `GET /v1/voices` and match by name
  (case-insensitive), raising a clear error listing available voices if not found.
- TTS call (`call_elevenlabs_tts`): `POST /v1/text-to-speech/{voice_id}` with
  `model_id`, and `voice_settings` = `stability`/`similarity_boost`/`style`/`use_speaker_boost`
  from config.
- Long scripts are chunked (`split_text_for_tts`, paragraph-aware, ≤ `max_chars_per_request`,
  default 4500) and the resulting MP3 parts are concatenated with `ffmpeg -f concat` into one
  file per lesson (`concat_audio_parts`).
- **Cost control**: existing `{slug}.mp3` files are skipped unless `overwrite_existing_audio`
  is true — a rerun (e.g. after switching modules and back) never re-buys narration by accident.
- Output: `output/audio/{lesson_slug}.mp3` + `output/manifests/audio_manifest.json` (with
  ffprobe-measured duration per lesson).

## 7. Video assembly (FFmpeg, `assemble_videos`)

- Requires both `ffmpeg` and `ffprobe` on PATH; refuses to run otherwise (clear error).
- **Slide timing is derived from the narration audio, not fixed per-slide**:
  `paragraph_weights()` maps each slide's `script_paragraph_indices` (set during slide-spec
  generation, e.g. the `map` slide covers paragraphs 0–3) to a character-length weight,
  enforces a floor (7s for the cover slide, 5.5s for others), then rescales all slide durations
  so they sum exactly to the measured audio duration.
- Renders one `ffmpeg -f concat` image sequence (`output/concat_lists/{slug}.txt`, listing each
  PNG with its computed `duration`) muxed against the lesson's MP3:
  `libx264 -preset veryfast -tune stillimage -pix_fmt yuv420p` video,
  `aac` audio at `video.audio_bitrate` (192k default), `-r 30`, `-shortest -movflags +faststart`.
- Skips re-encoding an existing MP4 unless `overwrite_existing_videos` is true (default `true`,
  unlike audio — video is treated as "cheap to redo since it's local compute", per the README's
  own cost-control framing).
- Output: `output/videos/{slug}.mp4` + `output/manifests/video_manifest.json`.

## 8. Trackers (`create_tracker`)

Two files per run under `output/trackers/`: a `.csv` and a formatted `.xlsx`
(openpyxl — maroon `#63192A` header fill, white bold header font, wrapped cell text, frozen
header row, column widths tuned per field). One row per lesson: course, module, lesson number/
title, script file, word/paragraph counts, audio file + runtime, slide count, video file, a
computed `Status` ("Video Ready" / "Audio Ready" / "Script/Slides Ready"), a path to that
lesson's individual Moodle description file, and a fixed reassurance note about exact script
preservation.

## 9. Moodle description generation (`generate_moodle_descriptions`)

**Text generation only — there is no Moodle API call anywhere in this codebase.** Per lesson,
it writes `output/moodle_descriptions/individual_lessons/{slug}.txt`: a templated paragraph
(lesson number/title heading, a fixed "Victory Framework" framing sentence, a `short_sentence()`
summary of the first narration paragraph, a comma-joined top-4 keyword line, the video filename,
and a `runtime_label()` mm:ss estimate from measured audio duration). All per-lesson texts are
also concatenated into one `module{N}_moodle_descriptions.md`. This is genuinely templated text
assembly (regex/string formatting against the real script), not an AI writer — the web version's
"AI can generate a description when the curriculum doesn't supply one" requirement is new
functionality layered on top, with this templated version kept as the always-available fallback.

## 10. Editable assets (`create_editable_assets`, `create_editable_pptx`)

Rebuilt from scratch every run (`shutil.rmtree` then recreate) at `output/editable_assets/{slug}/`:
- `editable_slides.pptx` — a 16:9 python-pptx deck reproducing each of the seven slide "kinds"
  as real editable shapes/text boxes (not an image export) using the identical brand palette
  constants, built by `create_editable_pptx()`. Gracefully skipped (with a manifest note) if
  `python-pptx` isn't installed.
  ```
  rendered_slides/    exact PNGs used in the video
  scripts/             copy of the narration .txt
  audio/                copy of the lesson MP3 (if present)
  video/                copy of the lesson MP4 (if present)
  slide_text.csv        per-slide type/eyebrow/title/body/items/paragraph-refs/seconds/image
  edit_notes.md         plain-language guidance on which file to use for which edit
  lesson_editing_manifest.json
  ```
  Plus a folder-level `editable_assets_index.csv` and `README_EDITABLE_ASSETS.md`.

## 11. Output organization & the review package

Everything lives under one `output/` tree (`ensure_dirs()` creates every subfolder up front):
`scripts, slides, audio, videos, concat_lists, trackers, moodle_descriptions, manifests, logs,
editable_assets, review_package`. `build_review_package()` assembles a clean delivery folder —
copies of the finished videos, trackers, the module Moodle-description doc + individual lesson
texts, all manifests, the editable-assets tree, and a generated `VALIDATION_SUMMARY.md` with
counts. `upload_to_drive()` optionally deep-copies that whole review package into a local Google
Drive Desktop sync folder — again, filesystem copy, not an API call.

## 12. Logging & run tracking

`Logger` (a tiny dataclass) timestamps every step to stdout and appends to a fresh
`output/logs/run_YYYYMMDD_HHMMSS.log` file per run. The pipeline is a strict linear sequence of
seven numbered steps (`Step 1/7` … `Step 7/7`, printed in `extract_scripts` → `render_slides` →
`generate_narration` → `assemble_videos` → `create_tracker` → `generate_moodle_descriptions` →
`upload_to_drive`, with `create_editable_assets` also inserted in `run_pipeline()`). There is
**no persisted step-level status beyond the log text and the manifests** — a failure partway
through has no structured "resume from here" state; you just rerun, and the cost-control
`overwrite_existing_*` flags happen to make that mostly safe (existing audio/video files are
reused). This lack of durable per-lesson state is exactly what the web version's job model has
to add.

## 13. Tests / validation materials

There is no automated test suite (no `tests/` folder, no `pytest` in `requirements.txt`).
"Validation" was manual: `VALIDATION_NOTES.md` documents a one-off dry run of Module 3
(4 lessons, 28 slides, trackers, Moodle text — narration/video intentionally skipped since
ElevenLabs was disabled) and a table confirming `select_module.py` correctly listed/activated
modules 2 and 3. I did not find anything to "run" as an automated check; I instead exercised
the real parser (`python-docx`) against the bundled `input_scripts/victory-framework-module2-
scripts.docx` directly to confirm the COURSE/MODULE/LESSON/TYPE block format documented above.

## 14. Dependencies (`requirements.txt`)

`pillow`, `openpyxl`, `python-docx`, `requests`, `python-pptx` — all pure-Python/cross-platform
wheels (Pillow ships prebuilt wheels for Linux/macOS/Windows; no OS-specific package in this
list). Plus `ffmpeg`/`ffprobe` on PATH as an external system dependency. **Nothing here requires
Windows** — this confirms the engine's portability is purely a matter of removing the `.bat`
launchers and the `%WINDIR%` font path, not rewriting any rendering logic.

## 15. What is preserved unchanged vs. what must change

| Preserve exactly (this is the reference output) | Must change (packaging/plumbing only) |
|---|---|
| Brand palette constants, card/vignette drawing, all 7 slide-kind renderers, header/footer chrome | `.bat` launchers → cross-platform CLI/Node job trigger |
| `make_slide_specs` content-selection heuristics | Global singleton `input_scripts/`/`output/` folders → per-job working directories |
| COURSE/MODULE/LESSON/TYPE + numbered-heading parsing | Font lookup: bundle brand fonts + platform fallback chain, drop `%WINDIR%` as primary |
| ElevenLabs request shape, voice resolution, chunking/concat | One global `config.json` → per-course brand/voice/integration settings resolved at job time |
| FFmpeg concat/timing math and encode flags | Google Drive Desktop copy step → real AWS S3 / Bunny Stream / Moodle API calls |
| Tracker XLSX/CSV layout, editable-asset export (PPTX/PNG/CSV/notes) | No persisted step state → durable per-lesson job/step status for retry |
| Templated Moodle description text (kept as fallback) | Parser extended (additively) for resources/descriptions/knowledge checks/course-level metadata |

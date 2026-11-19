# ARCHITECTURE.md — Victory Video Studio

This document covers the analysis required before writing code (Windows-specific vs.
preservable, see [`VIDEO_ENGINE.md`](VIDEO_ENGINE.md) for the full inspection) and the target
web architecture, with the reasoning behind each choice.

## 1. Summary of the inspection

The existing tool is a correct, working, good-looking single-user Windows batch pipeline. Its
Windows-ness is shallow (three `.bat` launchers plus one Windows-first font lookup); its real
value — the slide renderer, the parser, the ElevenLabs/FFmpeg pipeline, the tracker/Moodle-text/
editable-asset generation — is plain, portable Python with no OS-specific dependencies. See
`VIDEO_ENGINE.md` §15 for the exact preserve/change split. Nothing in this migration rewrites
the rendering logic; it wraps it.

## 2. Target architecture

```
Browser (React/Vite SPA)
        │  HTTPS
        ▼
Node.js API (Express + TypeScript)  ──serves the built SPA, owns auth/session
        │
        ├─ Postgres/SQLite (Prisma)  ──── the ONE authoritative content model
        │      Course → Module → Lesson → Asset, Job/JobStep, BrandTemplate,
        │      Voice, CurriculumDocument, ExternalMapping (S3/Bunny/Moodle)
        │
        ├─ Job queue (DB-backed; table-polling worker, see §3)
        │      one row per pipeline step per lesson → retryable, resumable
        │
        ├─ Worker process (Node)
        │      for engine steps: spawns `python -m victory_engine.cli <step>
        │      --job <json-file>` and reads back structured JSON on stdout
        │      for integration steps: calls AWS/Bunny/Moodle/ElevenLabs directly (Node)
        │
        ▼
Python engine (engine/victory_engine/*) — the preserved rendering code
        │
        ▼
FFmpeg (system binary, same commands as the original pipeline)

External services (called from Node, credentials server-side only):
  AWS S3 · Bunny Stream · Moodle REST (web services) · ElevenLabs (voice list/test;
  TTS synthesis itself stays in the Python engine, matching the original pipeline)
```

## 3. Key decisions, and why

**Node.js for the web app/API, Python only for rendering.** The brief allows either; Node is
the better fit here specifically because the web layer's job is upload handling, a relational
content model, a job queue, and three REST-ish integrations (S3, Bunny, Moodle) — none of that
benefits from being Python, and keeping the boundary at "Python renders, Node orchestrates"
means the 1,400 lines of slide/audio/video code in `pipeline.py` move with zero logic rewrite.

**The engine is invoked as a CLI subprocess per pipeline step, not as a long-running Python
service (no FastAPI/Flask sidecar).** A lesson's `extract → slides → narration → video →
editable-assets → tracker → moodle-text` steps are exactly the kind of thing that (a) needs
per-step retry without re-running earlier steps, (b) is naturally expressed as "run this one
step, write structured output, exit," and (c) benefits from OS-level process isolation — a
crashed FFmpeg encode for lesson 4 must not take down a service that's also mid-render for
lesson 5 of another course. A subprocess-per-step also means the job queue's own retry logic
(§4) is the only retry logic needed; there's no second in-process retry model to keep in sync
with it. The cost is subprocess spawn overhead per step (~tens of ms for Python startup),
which is irrelevant next to seconds-to-minutes of FFmpeg/ElevenLabs work per step.

**DB-backed job queue (a `job_steps` table + a polling worker loop), not Redis/BullMQ.** The
realistic concurrency here is "one person's courses, a handful of lessons rendering at a time,"
not a multi-tenant SaaS. A polling worker over Postgres/SQLite gives durable, query-able job
state (which is exactly what the "Production Dashboard" and "retry failed step" requirements
need — they're just a `SELECT` away) without adding a Redis dependency to the deployment. This
is documented as a deliberate scale trade-off: if concurrency needs grow, swap the worker loop
for BullMQ+Redis behind the same `JobStep` interface — nothing else changes.

**Prisma + SQLite by default, Postgres via `DATABASE_URL` override.** SQLite needs no separate
service to stand up the app locally or on a single Cloudways server; Prisma's schema is
DB-agnostic enough that moving to managed Postgres later is a one-line config change plus
`prisma migrate deploy`. Given this is a solo production tool today, that default minimizes
infrastructure without closing off growth.

**React + Vite + TypeScript for the frontend**, served as static files by the same Node app in
production (one deployable unit, one Cloudways app). Tailwind for styling speed; no heavier
framework (Next.js) needed since this isn't SSR/SEO-sensitive — it's an authenticated internal
tool.

**One central content model, external IDs stored as foreign attributes on it — never a
separate naming system.** `Lesson` rows carry `bunnyVideoId`, `awsKeyPrefix`,
`moodleActivityId`, etc. directly (or via a small `ExternalMapping` table keyed by
`(lessonId, provider)` — see `server/prisma/schema.prisma`). Every upload/publish step reads
its target path from the Course→Module→Lesson hierarchy already in the DB, so AWS keys, Bunny
titles, and Moodle placement are always derived, never entered twice.

## 4. Error recovery & smart regeneration model

Each lesson has a `JobStep` row per pipeline stage: `script → slides → narration → video →
editable_assets → resource → aws_upload → bunny_upload → moodle_publish`, each with its own
`status` (`queued/processing/complete/failed/error`) and `output` (JSON). A step only reruns
when (a) it is explicitly retried, or (b) a dependency it declares has changed:

| Change | Steps invalidated |
|---|---|
| Script edited | slides → narration → video → editable_assets → downstream uploads/publish |
| Video description / metadata edited | nothing rendering-related; only the Moodle publish payload is refreshed |
| Moodle destination changed | only `moodle_publish` |
| Resource edited | only that resource's generation + its AWS/Moodle steps |
| Brand template changed | slides → video (narration audio is reused) |
| Voice changed | narration → video |

This mirrors the original pipeline's own cost-control instinct (`overwrite_existing_audio`/
`overwrite_existing_videos` flags) but makes it structural and per-lesson instead of a single
global flag.

## 5. Curriculum versioning

On re-upload of a document already linked to a course, lessons are matched by
`(module_number, lesson_number)` first, then by title similarity as a fallback, and diffed by
hashing the extracted script text: `NEW` (no match), `CHANGED` (match, hash differs — regenerate
per §4), `UNCHANGED` (hash matches — skipped), `REMOVED` (existed before, absent now — flagged,
not auto-deleted). The diff is shown in the same import-preview UI used for first uploads.

## 6. Deployment shape (see DEPLOYMENT.md for the full Cloudways writeup)

The Node API + Postgres/SQLite + static frontend run fine as a normal Cloudways Node
application. FFmpeg encoding and ElevenLabs narration are CPU/time-bound and must **not** run
in the same process handling HTTP requests — they run in a separate long-lived worker process
(same server via `pm2`/systemd, or a second Cloudways app for the worker if load grows) so a
30-second video render never risks a web request timeout, and rendering load never starves the
UI. This is spelled out in detail, with the concrete resource/verification checklist, in
`DEPLOYMENT.md`.

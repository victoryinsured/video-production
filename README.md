# Victory Video Studio

A web application that turns a curriculum document into a fully produced, narrated, branded
course — video, slides, resources, and a published Moodle lesson — in one click.

Upload a DOCX/PDF/TXT/Markdown curriculum document, review how it was parsed into a
course/module/lesson structure, approve it, and click **Generate & Publish Entire Course**. The
app renders narrated slideshow video for every lesson, exports an editable PowerPoint deck,
uploads the video to AWS S3 and Bunny Stream, and publishes it into Moodle — tracking every step
so a failure anywhere can be retried without redoing finished work, and an edit anywhere only
re-renders what actually needs it.

This is a rewrite of a Windows-only desktop tool (`legacy/`) as a deployable web app. The
rendering engine's exact visual design (palette, slide layouts, timing algorithm) is preserved —
see `/VIDEO_ENGINE.md` for the full inspection of what the original tool did, and
`/ARCHITECTURE.md` for how this rewrite is shaped around it.

## The three pieces

| Directory | What it is |
| --- | --- |
| `engine/` | Python: curriculum parsing, Pillow slide rendering, ElevenLabs narration, ffmpeg video assembly, editable PPTX export. Invoked by the Node server as a subprocess, never run on its own. |
| `server/` | Node/Express API + a database-backed job queue. Two processes: the API (`npm run dev` / `npm start`) and the worker (`npm run worker`) that actually executes pipeline steps. |
| `web/` | React/Vite frontend: upload, course review, production dashboard, lesson editor, brand editor, voice library, diagnostics. |

## Quick start (local development)

```bash
# 1. Engine
cd engine
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest tests/ -q      # 18 tests should pass
cd ..

# 2. Server
cd server
npm install
cp ../.env.example .env                    # fill in at least SESSION_SECRET; see .env.example
npx prisma migrate deploy
npx prisma generate
npm run dev                                 # API on :4000
# in a second terminal:
npm run worker                              # job-queue worker — required, nothing renders without it
cd ..

# 3. Web
cd web
npm install
npm run dev                                 # :5173, proxies /api to :4000
```

Open http://localhost:5173, upload a curriculum document, and follow the Upload -> Courses ->
Dashboard flow. Every external integration (ElevenLabs, AWS, Bunny Stream, Moodle) is optional
for exploring the app — the Diagnostics page shows what's configured, and each one's Test
Connection button confirms it actually works before you trust it with a real course. See
`/INTEGRATIONS.md` for how to get each credential.

## How an edit propagates (smart regeneration)

Editing a lesson only re-renders what that edit could have actually changed:

- Edit the **script** -> re-renders slides and narration (and everything downstream: video,
  uploads, Moodle publish).
- Edit the **brand** -> re-renders slides and video, but narration audio is untouched.
- Edit the **voice** -> re-synthesizes narration and video, but slides are untouched.
- Edit the **video description only** -> nothing in the render pipeline re-runs; only the Moodle
  activity's description text changes on the next publish.

See `server/src/queue/pipeline.ts` for the exact dependency graph this is built from, and
`server/README.md` for the full pipeline diagram.

## Documentation map

- `/VIDEO_ENGINE.md` — inspection of the original Windows tool: what it did, what's preserved
  exactly, what changed and why.
- `/ARCHITECTURE.md` — why this rewrite is shaped the way it is (CLI-subprocess engine, DB-backed
  queue instead of Redis, single content model, curriculum versioning).
- `/INTEGRATIONS.md` — ElevenLabs/AWS/Bunny/Moodle credential setup and permissions.
- `/DEPLOYMENT.md` — what a host needs to run this (persistent processes, Python, ffmpeg), and a
  Cloudways/generic-VPS deployment walkthrough.
- `engine/README.md`, `server/README.md` — per-component source maps and commands.

## Tests

```bash
(cd engine && .venv/bin/python -m pytest tests/ -q)
(cd server && npm run typecheck && npm test)
(cd web && npm run build)   # runs tsc --noEmit, then the production build
```

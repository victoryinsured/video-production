# Victory Video Studio — Server

Node/Express API + DB-backed job queue. See /ARCHITECTURE.md at the repo root for why it's shaped
this way (no Redis/BullMQ, no long-running Python service, no CORS).

## Setup

```bash
npm install
cp ../.env.example .env   # then fill in at least DATABASE_URL, STORAGE_ROOT, ENGINE_DIR
npx prisma migrate deploy
npx prisma generate
```

`DATABASE_URL` for the default SQLite setup resolves relative to `prisma/schema.prisma`'s
directory, not your shell's cwd — `file:../data/victory.db` puts the database at
`server/data/victory.db`, matching `STORAGE_ROOT=./data`. Getting this wrong is the single most
common setup mistake; see DEPLOYMENT.md for the full explanation.

## Running

Two processes, both required:

```bash
npm run dev      # API server (src/index.ts), hot-reloading
npm run worker    # job-queue worker (src/queue/worker.ts) — polls JobStep, executes pipeline steps
```

In production: `npm run build && npm start` for the API, `npm run worker:build` for the worker
(run it under a process manager — systemd, pm2, Cloudways' own daemon support — so it restarts on
crash and on deploy).

## Tests

```bash
npm run typecheck   # tsc --noEmit
npm test            # vitest
```

## Source map

| Path | Responsibility |
| --- | --- |
| `src/env.ts` | All configuration, read once from `process.env`. |
| `src/db.ts` | The shared Prisma client singleton. |
| `src/paths.ts` | Storage layout + `sanitizeFilename` (the path-traversal guard — see its own doc comment). |
| `src/engine.ts` | Spawns `python -m victory_engine.cli` per pipeline step; parses its JSON stdout. |
| `src/auth.ts` | Single shared-password auth gate (no-op if `ADMIN_PASSWORD` unset). |
| `src/brandVoice.ts` | Brand/voice default resolution + dict conversion for the engine. |
| `src/curriculumDiff.ts` | NEW/CHANGED/UNCHANGED/REMOVED diff on document re-upload. |
| `src/slug.ts` | Mirrors `victory_engine.text_utils.slugify` so course slugs match on both sides. |
| `src/integrations/*.ts` | AWS S3, Bunny Stream, Moodle, ElevenLabs, and an optional AI-assist call. Each integration also exports a `test*Connection` used by the Diagnostics page. |
| `src/queue/pipeline.ts` | The step dependency graph; smart-regeneration invalidation; retry. |
| `src/queue/handlers.ts` | What each pipeline step actually does. |
| `src/queue/worker.ts` | The poll loop: claims a runnable pending step, executes it, records the result. |
| `src/routes/*.ts` | The REST API, one router per resource. |

## The pipeline, as a graph

```
slides ──┬─→ video ──┬─→ aws_upload ──┐
         │           │                 ├─→ moodle_publish
narration┘           └─→ bunny_upload ┘
         │
         └─→ editable_assets

resource_upload ──→ resource_moodle
```

Editing a lesson's script invalidates `slides` and `narration` (and therefore everything
downstream of either). Editing only the brand invalidates `slides` alone — `narration` and its
downstream `video` dependency on audio timing still have to wait for slides to re-render, but the
narration audio itself is never re-synthesized. Editing only the voice invalidates `narration`
alone, never touching `slides` or `editable_assets`. This is what "smart regeneration" means in
practice — see `src/queue/pipeline.ts` for the exact rules.

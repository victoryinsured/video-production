# Deployment

## What this app actually needs from a host

Before picking a host, it has to be able to run all of this, continuously, on one machine:

1. **A long-running Node.js process** (the API server, `server/`) — needs a persistent port, not
   a serverless/function-per-request model.
2. **A second, independent long-running Node.js process** (the job-queue worker,
   `server/src/queue/worker.ts`) — this is not optional. The worker is what actually executes
   pipeline steps; without it running continuously, nothing ever gets produced no matter how
   many times you click "Generate."
3. **Python 3.10+** with pip-installable packages (Pillow, python-docx, pypdf, python-pptx,
   openpyxl, requests) — invoked as a subprocess by the Node API, not as its own service.
4. **`ffmpeg` and `ffprobe` on `PATH`**, built with `libass` if you want burned-in captions
   (check with `ffmpeg -filters | grep subtitles`).
5. **Persistent local disk** for SQLite (`server/data/victory.db`) and rendered output
   (`server/data/output/...`) — this is not stateless; it cannot run on ephemeral/read-only
   filesystem storage without pointing `STORAGE_ROOT` and `DATABASE_URL` at a persistent volume.
6. Outbound HTTPS to ElevenLabs, AWS, Bunny Stream, and your Moodle site.

Any host that gives you a VPS-like environment (root/sudo SSH access, your own package installs,
the ability to run two always-on processes under a process manager) can run this. A purely
"upload PHP files" managed host cannot, regardless of brand.

## Cloudways specifically

Cloudways' core managed-application stacks are built around PHP applications (WordPress,
Laravel, Magento, "Custom PHP"). **Verify before committing to Cloudways** that your plan/server
type gives you: full SSH access to the underlying server, the ability to install system packages
(Python 3, ffmpeg) outside of what the managed PHP stack provides, and the ability to run two
persistent background processes (not just serve PHP-FPM requests) under something like
`systemd` or `supervisor`. Cloudways does offer non-PHP server provisioning (bringing up a plain
Ubuntu server on DigitalOcean/Vultr/AWS/GCP through their console) — if your account has that
option, treat it as a generic VPS and follow the steps below; the Cloudways dashboard then only
provides server monitoring/backups/firewall convenience on top of a normal Ubuntu box.
If you only have access to a managed PHP application stack, you will not be able to install
ffmpeg/Python/a second background worker there, and you should provision a plain VPS (Cloudways'
own "server" product, or a separate DigitalOcean/Linode/Vultr droplet) for this specific app
instead — there is no way around the process/runtime requirements above.

## Single-process hosts (Cloudways' Node.js app type)

Cloudways' Node.js application type manages exactly one process per app (start/stop/restart
through their dashboard, PM2 under the hood). Rather than fight that, set `RUN_WORKER_INLINE=true`
(see `.env.example`) — this runs the job-queue worker's poll loop inside the same process as the
API server (`server/src/index.ts`), so "one app" is all you need. The two-process (systemd) setup
further down is only necessary if you want the API and worker fully isolated from each other, e.g.
so a worker running a long video render can't affect API responsiveness.

Steps, via the SSH access your Cloudways dashboard gives you (Server -> Access Details/Master
Credentials, or Server -> SSH Keys to add your own key — exact tab names have moved around
Cloudways' UI over time, so check whichever your account currently shows):

```bash
ssh <ssh-user>@<your-server-ip>
cd applications/<your-app-id>/public_html   # the path your dashboard shows for this app

git clone <your-repo-url> .                  # or `git pull` if you've already cloned once

sudo apt-get update && sudo apt-get install -y python3 python3-venv ffmpeg   # if not already present

cd engine && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && cd ..

cd server
npm ci
cp ../.env.example .env
# edit .env: set SESSION_SECRET, ADMIN_PASSWORD, RUN_WORKER_INLINE=true, and whichever
# integration credentials you have — see /INTEGRATIONS.md
nano .env
npx prisma migrate deploy
npx prisma generate
npm run build
cd ..

cd web && npm ci && npm run build && cd ..
```

Then in the Cloudways dashboard's Application Settings for this app:
- Set the **startup file** to `server/dist/index.js`.
- Make sure the app's **Node version** is 18+ (20 recommended).
- Set **`NODE_ENV=production`** as an environment variable if your dashboard has an environment
  variables section for Node apps; otherwise it's already in `server/.env` and gets picked up
  from there.
- Click **Restart Application**.

Your Cloudways dashboard already shows a URL (your app's domain, or a temporary one Cloudways
assigns) — that's the real, working URL once the app restarts cleanly. Check the app's log
(Cloudways' dashboard has a log viewer for Node apps) for `Victory Video Studio API listening on
port ...` to confirm it actually started.

## Generic VPS setup (Ubuntu 22.04+, applies to Cloudways' own server product or any other VPS)

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv ffmpeg nginx git

# Node.js 20.x
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

git clone <your-repo-url> /opt/victory-video-studio
cd /opt/victory-video-studio

# Engine
cd engine
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd ..

# Server
cd server
npm ci
cp ../.env.example .env   # then edit .env — see /.env.example and /INTEGRATIONS.md
npx prisma migrate deploy
npx prisma generate
npm run build
cd ..

# Web
cd web
npm ci
npm run build             # outputs web/dist, served by the Express app in production
cd ..
```

### Running both processes under systemd

`/etc/systemd/system/victory-api.service`:

```ini
[Unit]
Description=Victory Video Studio API
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/victory-video-studio/server
EnvironmentFile=/opt/victory-video-studio/server/.env
ExecStart=/usr/bin/node dist/index.js
Restart=on-failure
User=www-data

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/victory-worker.service`:

```ini
[Unit]
Description=Victory Video Studio job-queue worker
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/victory-video-studio/server
EnvironmentFile=/opt/victory-video-studio/server/.env
ExecStart=/usr/bin/node dist/queue/worker.js
Restart=on-failure
User=www-data

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now victory-api victory-worker
sudo systemctl status victory-api victory-worker   # confirm both are "active (running)"
```

### nginx reverse proxy + TLS

```nginx
server {
    listen 80;
    server_name your-domain.example.com;

    location / {
        proxy_pass http://127.0.0.1:4000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 500M;   # must be >= the upload limits in server/src/routes/*.ts
    }
}
```

Then `sudo certbot --nginx -d your-domain.example.com` (via `apt install certbot
python3-certbot-nginx`) for a free TLS certificate.

## The DATABASE_URL gotcha

Prisma resolves a SQLite `file:` URL **relative to `server/prisma/schema.prisma`'s directory**,
not your shell's working directory when you run a command. With the repo's default
`DATABASE_URL="file:../data/victory.db"`, the real file ends up at `server/data/victory.db` —
one level up from `prisma/`, matching `STORAGE_ROOT=./data` (which *is* resolved relative to the
server process's cwd, normally `server/`). If you change one, check the other; a mismatch here
is the single most common setup mistake, and it fails silently — Prisma just creates a new empty
database wherever your (possibly wrong) path points.

## Upgrading to Postgres

Change two things in `server/prisma/schema.prisma`:

```prisma
datasource db {
  provider = "postgresql"   // was "sqlite"
  url      = env("DATABASE_URL")
}
```

Set `DATABASE_URL` to a real Postgres connection string, then `npx prisma migrate deploy` against
it. No application code changes needed — every query goes through Prisma.

## Security checklist before exposing a deployment to the internet

- [ ] `ADMIN_PASSWORD` is set (unset = no login screen at all, by design for local dev).
- [ ] `SESSION_SECRET` is a long random value, not the placeholder in `.env.example`.
- [ ] HTTPS is terminated (nginx + certbot, or your host's equivalent) — the session cookie isn't
      marked `secure` by name alone; serve this over HTTPS in production.
- [ ] `server/.env` is not committed and not web-readable (it isn't, by default: it lives outside
      `web/dist`, the only directory nginx/Express serves statically).
- [ ] AWS IAM credentials are scoped to the specific bucket(s) this app uses (see
      `/INTEGRATIONS.md`), not full account access.
- [ ] Outbound traffic to ElevenLabs/AWS/Bunny/your Moodle host is allowed by any firewall/egress
      rules on your VPS.

## Updating a running deployment

```bash
cd /opt/victory-video-studio
git pull
(cd server && npm ci && npx prisma migrate deploy && npm run build)
(cd web && npm ci && npm run build)
sudo systemctl restart victory-api victory-worker
```

The worker restart is safe at any time: a `JobStep` left `running` by a killed process (deploy
restart, crash, OOM-kill) is reset back to `pending` automatically the next time the worker
starts (`recoverOrphanedSteps()` in `server/src/queue/worker.ts`), so nothing gets permanently
stuck — the next poll picks it back up.

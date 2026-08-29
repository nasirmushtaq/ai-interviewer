# Deployment Guide

LinguaCall is **12-factor**: every URL, provider, and secret is read from
environment variables, so the same code runs locally, on a self-hosted Docker
host, or on managed PaaS. You deploy by pointing env vars at your prod
URLs/providers — no code changes.

## Services

| Service | What | Prod port |
|---|---|---|
| **web** | React SPA (Vite build → nginx) | 8080 |
| **api** | FastAPI core (auth, interviews, grading, vision) | 8000 |
| **media** | mediasoup SFU (optional; video/screen-share) | 4000 + UDP 40000-40100 |
| **piston** | code execution sandbox | 2000 |
| **db** | Postgres 16 | 5432 |
| **caddy** | reverse proxy + automatic HTTPS | 80/443 |

---

## Option A — Self-hosted Docker (single host, one command)

Prereqs: a VM with Docker + Docker Compose, DNS records for your domains, and the
UDP RTC port range open (only if you use the media SFU).

```bash
cp .env.prod.example .env.prod      # fill in domains, DB password, JWT_SECRET,
                                    # provider keys (Azure/OpenAI), tokens
./deploy.sh                         # build + start + install Piston runtimes
```

- Caddy issues Let's Encrypt certs for `APP_DOMAIN` and `API_DOMAIN` automatically.
- The **api** container runs `alembic upgrade head` on start (see
  `backend/docker-entrypoint.sh`), so the schema is always migrated.
- `./deploy.sh logs` / `./deploy.sh down` / `./deploy.sh ps` for ops.

Local test without real domains: set `APP_DOMAIN=:80` and `API_DOMAIN=:80` and
`PUBLIC_API_URL=http://localhost` in `.env.prod`.

---

## Option B — Managed PaaS

### Web → Vercel (or Netlify)
- Import the `frontend/` directory. `frontend/vercel.json` is preconfigured
  (Vite build, SPA rewrites).
- Set env var **`VITE_API_URL`** = your API origin (e.g. `https://api.example.com`).
  Vite inlines it at build time.

### API + Media → Render (blueprint) or Fly
- **Render:** point a Blueprint at `render.yaml` — it provisions the API (Docker),
  the media service, and a managed Postgres, wiring `DATABASE_URL` automatically.
  Set the secret env vars (provider keys, `CORS_ORIGINS`) in the dashboard.
- **Fly:** `fly.toml` deploys the API. Create/attach Postgres with
  `fly postgres create && fly postgres attach`, then
  `fly secrets set AZURE_OPENAI_API_KEY=… JWT_SECRET=… CORS_ORIGINS=…` and `fly deploy`.

### Database
Any managed Postgres works. Set `DATABASE_URL`; the app normalizes
`postgres://` / `postgresql://` to the psycopg driver automatically. Run
migrations once (the Docker entrypoint does this, or `alembic upgrade head`).

### Code execution (Piston)
Run Piston as its own container/host and set `PISTON_URL`, or point at a Piston
instance you control. (The public `emkc.org` Piston is rate-limited — self-host
for production.)

---

## Required environment variables (API)

| Var | Purpose |
|---|---|
| `ENV` | `production` in prod (disables SQLite auto-create; expects migrations) |
| `DATABASE_URL` | Postgres URL in prod (SQLite default in dev) |
| `CORS_ORIGINS` | comma-separated web origins (e.g. `https://app.example.com`) |
| `JWT_SECRET` | long random string for signing auth tokens |
| `REQUIRE_AUTH` | `true` to force login on protected endpoints |
| `PISTON_URL` | code-execution service URL |
| `MEDIA_SERVICE_URL` / `MEDIA_SERVICE_TOKEN` | media SFU URL + shared token |
| `RATE_LIMIT_LLM` / `RATE_LIMIT_EXEC` | e.g. `30/minute`, `20/minute` |
| **Provider** (one of) | Azure: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_CHAT_DEPLOYMENT` · or `OPENAI_API_KEY` · or `GITHUB_TOKEN` |

The provider is **auto-detected** from whichever credentials are present (see
`backend/app/config.py`). `GET /api/health` reports the active provider.

---

## Production checklist
- [ ] `.env.prod` filled; secrets NOT committed (they're gitignored)
- [ ] `JWT_SECRET` set to a strong random value; `REQUIRE_AUTH=true` if desired
- [ ] `CORS_ORIGINS` set to your real web origin(s)
- [ ] `DATABASE_URL` → managed Postgres; migrations applied
- [ ] Provider keys set; `GET /api/health` shows the right provider
- [ ] Piston reachable at `PISTON_URL` with Python/Java/C++ installed
- [ ] (If using video) `MEDIA_ANNOUNCED_IP` = server public IP, UDP ports open

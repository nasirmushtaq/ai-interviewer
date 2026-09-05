# Deploy guide — cheap/free stack (Render + Neon + Upstash + Kimi)

This deploys the AI interviewer for **~$0/month infra** (you pay only LLM tokens).

Stack:
- **Backend + Frontend** → Render (free web services)
- **Postgres** → Neon (free tier)
- **Redis** → Upstash (free tier) *(optional — in-memory fallback works on 1 instance)*
- **LLM** → Kimi K2 (Moonshot) for reasoning + OpenAI **for diagram vision only**
- **Code execution (Piston)** → skip for now (only needed for the coding round; the
  System Design product doesn't need it)

---

## 1. Postgres (Neon) — free

1. Create a project at https://neon.tech → copy the connection string.
2. Convert it to the SQLAlchemy async-safe form:
   `postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require`

## 2. Redis (Upstash) — free, optional

1. Create a database at https://upstash.com → copy the **redis:// URL** (with password).
2. Set `REDIS_URL` to it. *If you skip this, leave `REDIS_URL` blank — the app uses a
   single-instance in-memory fallback (fine for one backend instance).*

## 3. LLM keys

- **Kimi K2 (Moonshot)**: get an API key at https://platform.moonshot.ai
  - `CUSTOM_LLM_BASE_URL=https://api.moonshot.ai/v1`
  - `CUSTOM_LLM_CHAT_MODEL=kimi-k2-0711-preview` (or the current K2 model id)
- **OpenAI** (vision only — reading the whiteboard diagram): key from
  https://platform.openai.com → `OPENAI_API_KEY=sk-...`
  - Kimi K2 can't read images, so `VISION_PROVIDER=openai` routes ONLY diagram
    analysis to GPT-4o. Everything else runs on Kimi. If you don't want any vision,
    leave `VISION_PROVIDER` blank and the interviewer works from the structured
    diagram graph alone (text) — no OpenAI needed.

## 4. Generate a JWT secret (REQUIRED)

```bash
openssl rand -hex 32
```
The app **refuses to boot in production** with the default/weak secret.

---

## 5. Backend on Render

Create a **Web Service** from your repo, root = `backend/`:
- **Build**: `pip install -r requirements.txt`
- **Start**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT` (the schema is created from the models on startup)
- **Environment variables**:

```
ENV=production
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require
REDIS_URL=redis://default:PASSWORD@HOST:PORT      # or leave blank
JWT_SECRET=<openssl rand -hex 32 output>
CORS_ORIGINS=https://YOUR-FRONTEND.onrender.com   # exact origin, no '*'

# LLM (Kimi primary + OpenAI vision)
LLM_PROVIDER=custom
CUSTOM_LLM_BASE_URL=https://api.moonshot.ai/v1
CUSTOM_LLM_API_KEY=sk-moonshot-...
CUSTOM_LLM_CHAT_MODEL=kimi-k2-0711-preview
VISION_PROVIDER=openai
OPENAI_API_KEY=sk-openai-...

# Product config
ENABLED_TRACKS=sde
ENABLE_PERSONA_CALLS=false
FREE_INTERVIEW_QUOTA=2
DEV_ALLOW_TEST_PAYMENTS=false        # MUST be false in prod

# Payments (optional — set when you go live with billing)
PAYMENT_PROVIDER=razorpay
RAZORPAY_KEY_ID=...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
```

> The startup guard will **refuse to boot** if `JWT_SECRET` is default/short, if
> `CORS_ORIGINS` is `*`, or if no LLM is configured — this is intentional.

## 6. Frontend on Render

Create a **Static Site** from your repo, root = `frontend/`:
- **Build**: `npm ci && npm run build`
- **Publish dir**: `dist`
- **Environment**: `VITE_API_URL=https://YOUR-BACKEND.onrender.com`
- Add a rewrite rule: `/*  →  /index.html` (SPA fallback).

Then set the backend's `CORS_ORIGINS` to the static site's URL.

---

## 7. Post-deploy checklist

- [ ] Backend `/api/config` returns `provider: custom`, `enabled_tracks: ["sde"]`.
- [ ] Register a user, log in, start a System Design interview end-to-end.
- [ ] Whiteboard analysis works (diagram → interviewer reacts). If you set
      `VISION_PROVIDER=openai`, confirm OpenAI billing shows only vision calls.
- [ ] `DEV_ALLOW_TEST_PAYMENTS` is **false**; the test-pay button is gone.
- [ ] Try `/api/login` (legacy) → returns 410 in prod (disabled).
- [ ] Hammer `/api/auth/login` → gets rate-limited (429) after the configured rate.

## Notes on cost
- Render free web services **spin down when idle** → first request after idle is
  slow (cold start). Fine for early users; upgrade to the $7/mo instance to avoid it.
- Neon/Upstash free tiers are generous for early traffic.
- You pay only **LLM tokens**. Kimi K2 is cheap; note the interviewer makes an extra
  small "coverage" call per design turn (thorough interviews = more tokens). Vision
  (OpenAI) is called only when the candidate shares the whiteboard.

## Alternative one-box option
`docker-compose.prod.yml` runs the whole stack (api + frontend + Postgres + Redis +
Piston + Caddy TLS) on a single cheap VPS (e.g. Hetzner ~€4/mo) if you prefer
self-hosting everything. See `DEPLOY.md`.

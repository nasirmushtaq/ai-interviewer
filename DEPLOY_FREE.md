# Deploy for free (no credit card): Render + Neon + Vercel

This ships the whole app on free tiers, with **no payment method required**:

| Piece | Host | Cost |
|---|---|---|
| Frontend (Vite SPA) | **Vercel** | free |
| API + media (Docker) | **Render** free web services | free (cold-starts on idle) |
| Postgres | **Neon** | free |
| Code execution | **public Piston API** | free, nothing to host |
| Redis | *omitted* — in-memory fallback | — |

> ⚠️ **Cold starts:** Render free services sleep after ~15 min idle; the next
> request wakes them in ~30–50s. Fine for a demo/portfolio. For always-on, bump
> the two services to `plan: starter` (~$7/mo each) in `render.yaml`.

---

## 1. Postgres on Neon
1. Sign up at https://neon.tech (GitHub login, no card).
2. Create a project → copy the **pooled** connection string
   (`postgresql://user:pass@...neon.tech/db?sslmode=require`).
3. Keep it handy for step 2 (`DATABASE_URL`). Tables are created automatically
   from the models on first API startup — no migration step.

## 2. API + media on Render
1. Sign up at https://render.com (no card for free tier).
2. **New → Blueprint**, point it at this repo. Render reads [`render.yaml`](render.yaml)
   and creates `linguacall-api` + `linguacall-media`.
3. Set the `sync: false` secrets on **linguacall-api** in the dashboard:
   - `DATABASE_URL` = the Neon string from step 1
   - `CORS_ORIGINS` = your Vercel URL (fill in after step 3, e.g.
     `https://linguacall.vercel.app`) — **not** `*`
   - Provider: either `OPENAI_API_KEY`, **or** the four `AZURE_OPENAI_*` vars
   - `JWT_SECRET` / `MEDIA_SERVICE_TOKEN` are auto-generated
   - `PISTON_URL` is preset to the public API — leave it
4. Deploy. Health check: `https://linguacall-api.onrender.com/api/health`
   should return `{"ok": true, ...}`.

> The API **refuses to start** in production if `JWT_SECRET` is weak or
> `CORS_ORIGINS` is `*` — that's the startup guard doing its job.

## 3. Frontend on Vercel
1. Sign up at https://vercel.com (no card).
2. **Add New → Project**, import this repo.
3. Set **Root Directory** to `frontend`. Vercel picks up
   [`frontend/vercel.json`](frontend/vercel.json) (Vite + SPA rewrites).
4. Add an environment variable:
   - `VITE_API_URL` = `https://linguacall-api.onrender.com` (your Render API URL)
5. Deploy, then copy the resulting URL back into the API's `CORS_ORIGINS`
   (step 2.3) and redeploy the API so CORS matches.

## 4. Smoke test
- Open the Vercel URL, register an account, start a text or voice interview.
- First request may be slow (Render cold start) — that's expected on free.
- Try the coding round to confirm the public Piston execution works.

---

## Notes & limits
- **Realtime voice** needs a provider that offers it (OpenAI/Azure realtime).
  Without it, the app falls back to the free on-device browser voice.
- **Single instance**: Redis is omitted, so live observation pub/sub uses the
  in-memory fallback — fine for one API instance. Add `REDIS_URL` (Upstash has a
  free tier) if you scale to multiple instances.
- **Media service** (camera/screen vision) also cold-starts; the core interview
  works without it.

# 🗣️ LinguaCall

> **Deploying to production?** See [DEPLOY.md](./DEPLOY.md) — env-driven config for self-hosted Docker (`./deploy.sh`) or managed PaaS (Vercel + Render/Fly + Postgres).

Learn English by **actually getting on a voice call** with an AI that feels like a
real person on the other end — one that **remembers your past conversations** and
lets you switch between different **personas**. It can also flip into an
**AI technical interviewer** that asks real SDE questions (DSA / System Design /
LLD / Behavioral), then grades you and gives real feedback like an actual reviewer.

Built **backend-first** and client-agnostic so the same API powers a **web app**
or a **native mobile app**. It supports **voice + video + screen-share**, so the
AI interviewer can actually *see* the candidate and their screen (code editor,
whiteboard, terminal) while asking questions.

Stack: **FastAPI + SQLite** (Core API), **Node + mediasoup** (media SFU), and the
**OpenAI Realtime API over WebRTC** for natural voice, plus **GPT-4o vision** for
seeing camera/screen frames. A React + Vite web client is included.

---

## ✨ Features

- **Persona voice calls** — Call Emma, Raj, Sofia (a gentle tutor) or Mike over
  real mic-in / AI-voice-out WebRTC, with a live transcript.
- **Long-term memory** — After each call the backend summarizes it and extracts
  durable facts, injected into future calls so your AI friends remember you.
- **AI Interviewer with eyes 👀** — Video + screen-share flow: the candidate's
  webcam and shared screen are streamed to a media SFU, which samples frames and
  feeds them to GPT-4o vision. The interviewer reacts to what's on screen (your
  code, diagram, errors) and your engagement — like a real video interview.
- **Rich, data-driven interview catalog** — Choose a **track**
  (SDE ▸ DSA / System Design / LLD / Behavioral, **UPSC**, **Product Manager**,
  **Data Science/ML**, **Data Analyst**, **Aptitude**, or a fully **custom** one),
  a **company/board** (Google, Amazon, Meta, Microsoft, Apple, Startup, UPSC Board,
  or any free-text name like "Netflix"), and a **difficulty** (easy/medium/hard).
  The questions, follow-up depth, and grading strictness all adapt accordingly.
  Adding a new track or company is just a dict entry in `backend/app/catalog.py`.
- **Deep, staged design interviews** — For design focuses the interviewer runs a
  realistic **drill-down ladder**: requirements → high-level architecture → deep
  dive → **implementation / LLD** (schema, classes, core algorithm) → edge cases.
  Great for problems like *"Design a payment gateway"* or *"Design a bank's money
  transfer"*, going from system level down to concrete implementation.
- **Optional tiered hints that cost points** — Stuck? Ask for a hint: **Nudge (−5)**,
  **Approach (−12)** or **Partial solution (−22)**. Hints are AI-generated for your
  current question, logged, and **transparently reduce your score** — or disable
  hints entirely for a no-help, no-penalty run. The report shows where you needed help.
- **Coding round with a real editor** — A **Monaco** (VS Code) editor with
  **Python / Java / C++**, problems (seeded + AI-generated) with **visible example
  tests** and **hidden tests**, and **real execution** via self-hosted **Piston**.
  Run against examples to debug, Submit to run hidden tests too; correctness feeds
  the grade (hidden inputs are never revealed).
- **Design whiteboard** — For system-design / LLD, an in-app **Excalidraw**
  whiteboard: draw your architecture, share it, and the interviewer *sees* it via
  GPT-4o vision and reacts to your diagram.
- **Graded feedback** — A structured report (overall + per-dimension scores,
  strengths, improvements, written assessment) that folds in the visual
  observations captured during the interview.
- **Client-agnostic API** — See [`API.md`](./API.md); web or native app can drive it.

---

## 🏗️ Architecture (two backend services)

```
                         ┌──────────────────────────────┐
  Web / Native client ──►│ Core API  (FastAPI, :8000)    │
      │   │              │  auth, sessions, realtime      │
      │   │              │  token, GPT-4o VISION on        │
      │   │              │  frames, memory, grading        │
      │   │              └──────────────▲─────────────────┘
      │   │  voice (WebRTC, direct)     │ POST /frames (JPEG)
      │   ▼                             │ (X-Media-Token)
      │  OpenAI Realtime API            │
      │                                 │
      │  camera + screen (WebRTC)  ┌────┴─────────────────────┐
      └───────────────────────────►│ Media SFU (Node+mediasoup│
                                    │ :4000) samples frames    │
                                    │ via ffmpeg               │
                                    └──────────────────────────┘
```

- The client streams **camera** and **screen** tracks to the **Media SFU**.
- The SFU decodes the video RTP with **ffmpeg**, grabs a JPEG every few seconds,
  and POSTs it to the **Core API**, which runs **GPT-4o vision** and stores an
  observation — also pushed live to the client over a WebSocket.
- **Voice** stays low-latency by connecting the client **directly** to OpenAI
  with an ephemeral token minted by the Core API.
- Grading pulls the session's visual observations into the final report.

---

## 🚀 Setup & Run

### Prerequisites
- Node 18+, Python 3.10+, and **ffmpeg** on PATH (used for frame extraction)
- An **OpenAI API key** with Realtime + vision access

### 1. Core API (FastAPI)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # add OPENAI_API_KEY; keep MEDIA_SERVICE_TOKEN
uvicorn app.main:app --reload --port 8000
```

### 2. Media SFU (Node + mediasoup)

```bash
cd media
npm install                          # builds the native mediasoup worker
cp .env.example .env                 # MEDIA_SERVICE_TOKEN must match backend/.env
npm run dev                          # http://localhost:4000/health
```

### 3. Code execution (Piston, for the coding round)

```bash
docker compose -f piston/docker-compose.yml up -d
bash piston/install-runtimes.sh        # installs Python, Java, C++ (once)
curl http://localhost:2000/api/v2/runtimes   # verify
```
See `piston/README.md`. The backend uses `PISTON_URL` (default
`http://localhost:2000`).

### 4. Web client

```bash
cd frontend
npm install
npm run dev                          # http://localhost:5173
```

> Without an OpenAI key the services still boot; voice, vision and grading are
> disabled (the API returns clear stubs/400s). ffmpeg is required for the SFU to
> sample frames. For non-local hosting, set `MEDIASOUP_ANNOUNCED_IP` and open the
> UDP RTC port range (see `media/.env.example`).

See [`API.md`](./API.md) for the full request/response contract and the exact
video/screen-share signaling flow a native app would implement.

---

## 🔑 Environment (`backend/.env`)

| Variable | Purpose | Default |
|---|---|---|
| `OPENAI_API_KEY` | Your OpenAI key (required for voice/memory/grading) | — |
| `OPENAI_TEXT_MODEL` | Model for grading & memory extraction | `gpt-4o` |
| `OPENAI_REALTIME_MODEL` | Realtime voice model | `gpt-4o-realtime-preview` |
| `FRONTEND_ORIGIN` | CORS origin for the frontend | `http://localhost:5173` |
| `DATABASE_URL` | SQLite database URL | `sqlite:///./linguacall.db` |

> Without a key the app still runs and the UI loads; live calls, memory and
> grading are disabled (you'll see a banner). Add a key to unlock them.

---

## 🧭 Using it

1. Enter a username on the home page.
2. **Practice English:** pick a persona → **Call** → allow mic → talk. Hang up and
   it saves a summary + new memories. Next time, they'll remember you.
3. **Mock interview:** go to **Interview**, choose role/focus/difficulty → enter the
   room → **Start interview** → answer out loud → **End & get feedback** for a graded
   report.
4. **Dashboard:** review memories, reports and past conversations.

---

## 📁 Project layout

```
ai-interviewer/
├── API.md                      # full client-agnostic API contract
├── backend/                    # Core API (FastAPI + SQLite)
│   ├── app/
│   │   ├── main.py            # app + REST routes
│   │   ├── sessions.py        # session lifecycle, frame ingest, observe WS
│   │   ├── vision_service.py  # GPT-4o vision on camera/screen frames
│   │   ├── catalog.py         # tracks, company profiles, difficulty specs
│   │   ├── openai_service.py  # realtime token, chat, vision, JSON helpers
│   │   ├── services.py        # memory extraction + interview grading
│   │   ├── personas.py        # personas + prompt builders
│   │   ├── db.py              # models: users, sessions, observations, …
│   │   └── config.py
│   └── requirements.txt
├── media/                      # Media SFU (Node + mediasoup)
│   └── src/
│       ├── server.js          # HTTP health + WebSocket signaling
│       ├── room.js            # per-session router/transports/producers
│       ├── mediasoup.js       # worker/router/transport setup
│       ├── frameSampler.js    # RTP -> ffmpeg -> JPEG -> Core API
│       └── config.js
└── frontend/                   # React + Vite web client
    └── src/…
```

---

## 🔒 Notes

This is a prototype: simple username-based sessions and SQLite. For production,
add real authentication, a managed database (e.g. Postgres), rate limiting, and
move secrets to a proper secrets manager. Voice quality/latency depend on your
network and OpenAI Realtime availability.

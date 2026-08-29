# LinguaCall API Contract

Client-agnostic contract for the **web app** and a future **native mobile app**.
Two backend services:

| Service | Tech | Port | Role |
|---|---|---|---|
| **Core API** | FastAPI (Python) | 8000 | Auth, sessions, realtime voice tokens, **AI vision on frames**, memory, grading, history |
| **Media (SFU)** | Node + mediasoup | 4000 | Receives candidate **camera + screen** WebRTC tracks, samples frames, POSTs them to the Core API |

The client talks HTTP/WS to the Core API for everything except raw media, and
WS+WebRTC to the Media service to publish its camera/screen. Voice still connects
the client **directly to OpenAI Realtime** using an ephemeral token from the Core API.

---

## Interview call flow (end to end)

```
1. POST /api/sessions                      -> { session_id, media_service_url }
2. POST /api/realtime/session (mode=interview, session_id in appData)
                                           -> ephemeral token; client opens voice
                                              call directly to OpenAI (WebRTC)
3. WS  {media}/ws : join(session_id) -> createTransport -> connect -> produce
       (produce camera video with appData.source="camera",
        produce screen video with appData.source="screen")
4. Media service samples frames every N s and calls
   POST /api/sessions/{id}/frames          -> GPT-4o vision -> Observation saved
5. WS  /api/sessions/{id}/observe          -> client receives live observations
6. POST /api/interview/grade { session_id, transcript }
                                           -> report folds in observations
```

---

## Core API (port 8000)

### `GET /api/config`
Bootstrap config for any client.
```json
{ "has_openai_key": true, "media_service_url": "http://localhost:4000",
  "video_supported": true, "screenshare_supported": true }
```

### `POST /api/login`  → `{ id, username }`
Body: `{ "username": "nasir" }`

### `POST /api/sessions`
Create a live session (interview or persona).
```json
// body
{ "username": "nasir", "mode": "interview",
  "role": "SDE", "focus": "dsa", "difficulty": "medium" }
// response
{ "session_id": "…hex…", "media_service_url": "http://localhost:4000",
  "status": "active" }
```

### `GET /api/sessions/{session_id}`
Returns session state + all visual observations.
```json
{ "session_id":"…","mode":"interview","status":"active",
  "role":"SDE","focus":"dsa","difficulty":"medium",
  "observations":[{"source":"screen","note":"Candidate is editing a Python
     function in VS Code.","flags":[],"at":"…"}] }
```

### `POST /api/sessions/{session_id}/frames`  *(media service only)*
Header `X-Media-Token: <MEDIA_SERVICE_TOKEN>`. One sampled frame → GPT-4o vision.
```json
// body
{ "source": "camera" | "screen",
  "image": "data:image/jpeg;base64,…",
  "hint": "optional context string" }
// response (also broadcast on the observe WS)
{ "type":"observation","source":"screen",
  "note":"…what the AI saw…","flags":["compile_error_visible"],"at":"…" }
```

### `WS /api/sessions/{session_id}/observe`
Server pushes JSON messages:
`{ "type":"connected", … }` then `{ "type":"observation", "source", "note", "flags", "at" }`.

### `POST /api/realtime/session`
Mints an OpenAI Realtime ephemeral token. Body:
`{ username, mode, persona_id?, role?, focus?, difficulty? }`.
Returns OpenAI's session object (client uses `client_secret.value`).

### `POST /api/interview/grade`
```json
// body — pass session_id to fold in visual observations
{ "username":"nasir","role":"SDE","focus":"dsa","difficulty":"medium",
  "session_id":"…","transcript":[{"role":"assistant","text":"…"},
                                  {"role":"user","text":"…"}] }
// response
{ "id":1,"overall_score":72,
  "scores":{"problem_solving":70,"technical_depth":68,
            "communication":80,"correctness":70},
  "strengths":["…"],"improvements":["…"],"feedback":"…" }
```

### Other
- `GET /api/personas`, `GET /api/interview/focuses`
- **Catalog** (see below): `GET /api/catalog/tracks`, `/api/catalog/companies`, `/api/catalog/difficulties`
- `POST /api/chat` (text fallback), `POST /api/conversations` (persona memory)
- `GET /api/history/{username}`
- Full interactive docs at `http://localhost:8000/docs`.

---

## Coding round (editor + tests + execution)

Backed by self-hosted **Piston** (see `piston/README.md`). Languages: Python,
Java, C++.

### `GET /api/sessions/coding/languages`
`[{ "id":"python","label":"Python 3.10","monaco":"python" }, …]`

### `POST /api/sessions/{id}/problem`
Get/assign a coding problem (hybrid: a seeded problem or AI-generated). Body:
`{ "seed_id"?: "two_sum_indices", "topic"?: "strings" }`.
```json
// response — hidden tests are NEVER returned, only their count
{ "id":"…","title":"Pair Sum","difficulty":"easy","statement":"…",
  "starter":{"python":"…","java":"…","cpp":"…"},
  "examples":[{"input":"…","expected":"…"}], "hidden_count":3 }
```

### `POST /api/sessions/{id}/run`
Run code against the **visible example tests only**.
`{ "language":"python", "source":"…" }` →
```json
{ "results":[{"input","expected","stdout","stderr","status","passed"}],
  "passed":2, "total":2 }
```

### `POST /api/sessions/{id}/submit`
Run against **example + hidden** tests. Hidden inputs are redacted.
```json
{ "results":[ …examples…, {"hidden":true,"passed":true,"status":"Accepted"} ],
  "example_passed":2,"example_total":2,"hidden_passed":3,"hidden_total":3,
  "passed":5,"total":5 }
```
Submit results are stored on the session and folded into the interview grade
(correctness reflects real test outcomes).

---

## Design whiteboard (vision)

### `POST /api/sessions/{id}/diagram`
Send a PNG snapshot of the in-app whiteboard (or any diagram). It is analyzed by
GPT-4o vision (same pipeline as screen frames), stored as an observation, and
streamed on the observe WS. Set `final: true` to keep it for the report.
`{ "image":"data:image/png;base64,…", "final":false }` →
`{ "note":"A load balancer connects to a database…", "flags":[] }`

---

## Interview catalog (tracks, companies, difficulty)

Interviews are configured along four data-driven axes. The client fetches the
catalog, lets the user choose, and passes the choices to `POST /api/sessions`
(and/or `realtime/session` and `interview/grade`).

### `GET /api/catalog/tracks`
Every track with its focus areas.
```json
[ { "id":"sde","name":"Software Engineer (SDE)","emoji":"💻",
    "focuses":[{"id":"dsa","brief":"…"},{"id":"system_design","brief":"…"},
               {"id":"lld","brief":"…"},{"id":"behavioral","brief":"…"}] },
  { "id":"upsc","name":"UPSC / Civil Services","emoji":"🏛️",
    "focuses":[{"id":"personality",…},{"id":"current_affairs",…},
               {"id":"optional_subject",…},{"id":"situational",…}] },
  { "id":"pm", … }, { "id":"data_science", … }, { "id":"data_analyst", … },
  { "id":"aptitude", … }, { "id":"generic","name":"Custom / Other", … } ]
```
Built-in tracks: **sde, upsc, pm, data_science, data_analyst, aptitude, generic**.
`generic` adapts to any free-text role/topic.

### `GET /api/catalog/companies`
Curated company/board profiles: **google, amazon, meta, microsoft, apple,
startup, upsc_board**. A client may instead send a free-text `company_name`
(e.g. "Netflix") — the interviewer emulates that company's known style.

### `GET /api/catalog/difficulties`
`easy | medium | hard` — each shifts **question hardness**, **follow-up depth**,
and **grading strictness** (and the grader's rough passing bar).

### `GET /api/catalog/design-topics`
Suggested staged-design problems (Payment gateway, Core banking, Rate limiter,
Ride-sharing, …). Any free-text topic also works via `candidate_note`.

### `GET /api/catalog/hint-tiers`
The tiered hint model: `1 Nudge (−5)`, `2 Approach (−12)`, `3 Partial solution (−22)`.

### Staged design drill-down
When `focus` is a design focus (`system_design`, `lld`, `case_study`), the
interviewer runs a realistic **ladder**: requirements → high-level architecture →
deep dive → **implementation / LLD** (schema, classes, core algorithm) → edge
cases. Pass the concrete system in `candidate_note` (e.g. *"Design a payment
gateway"*).

### Hints — `POST /api/sessions/{id}/hint`
Candidate-requested, tiered, and score-costing. (403 if the session was created
with `hints_enabled: false`.)
```json
// body
{ "tier": 2, "question_context": "designing idempotency", "transcript": [ … ] }
// response
{ "tier":2, "label":"Approach", "penalty":12,
  "text":"Think about how to make each charge attempt idempotent…",
  "hints_used":1, "total_penalty":12 }
```
Hints are logged on the session; at grading time the raw score is reduced by the
total penalty and the report records `hints_used` / `hint_penalty`.

### How the axes flow through the API
`POST /api/sessions` (and `realtime/session`, `interview/grade`) accept:
```json
{ "track":"sde", "focus":"system_design", "difficulty":"hard",
  "company_id":"google",           // OR:
  "company_name":"Netflix",         // free-text fallback
  "role":"Senior Backend Engineer",
  "hints_enabled":true,             // false = no hints, no penalty
  "candidate_note":"Design a payment gateway" }
```
The backend composes the interviewer's system prompt from
**track + focus + company/board style + difficulty**, and the grader calibrates
strictness to the difficulty and company bar. Setup is stored on the session, so
`interview/grade` with just a `session_id` grades with the right context and the
report records `track`, `focus`, `company` and `difficulty`.

---

## Media service (port 4000)

### `GET /health` → `{ ok, service, rooms }`

### `WS /ws` — signaling (JSON `{ id, action, data }`, reply `{ id, ok, data|error }`)

| action | data | reply |
|---|---|---|
| `join` | `{ sessionId }` | `{ rtpCapabilities }` |
| `createTransport` | `{ direction:"send" }` | WebRTC transport params (id, ice, dtls) |
| `connectTransport` | `{ transportId, dtlsParameters }` | `{ connected:true }` |
| `produce` | `{ transportId, kind, rtpParameters, appData:{source:"camera"\|"screen"\|"mic"} }` | `{ id }` |

A **video** `produce` automatically attaches a server-side frame sampler that
decodes the VP8 RTP with ffmpeg and POSTs JPEG frames to the Core API. Use
`appData.source` to label a track as the webcam (`camera`) or the shared screen
(`screen`). The client should use `mediasoup-client` (`Device` + `createSendTransport`)
and wire its `connect`/`produce` events to the matching WS actions above.

---

## Auth & security notes (prototype)
- Username-based sessions; no passwords yet. Add real auth for production.
- `MEDIA_SERVICE_TOKEN` must match in `backend/.env` and `media/.env`.
- For non-local deployments set `MEDIASOUP_ANNOUNCED_IP` to the server's public
  IP and open the `RTC_MIN_PORT`–`RTC_MAX_PORT` UDP range.

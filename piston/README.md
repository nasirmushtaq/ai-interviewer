# Piston — code execution for the coding round

Self-hosted [Piston](https://github.com/engineer-man/piston) sandboxes candidate
code (Python / Java / C++) for the interview coding round. Chosen over Judge0
because it works on modern Docker (cgroup v2) hosts without global changes.

## Start it

```bash
docker compose -f piston/docker-compose.yml up -d
# wait ~8s, then install the language runtimes (first time only):
bash piston/install-runtimes.sh
```

`install-runtimes.sh` installs:
- Python 3.10, Java 15, and **gcc 10.2** (which provides C++).

Verify:
```bash
curl -s http://localhost:2000/api/v2/runtimes
# should list python, java, c++
```

The Core API talks to Piston at `PISTON_URL` (default `http://localhost:2000`,
set in `backend/.env`).

## How execution flows
- `POST /api/sessions/{id}/run`  → runs the candidate's code against the
  **visible example tests**; returns per-test stdout/stderr/verdict.
- `POST /api/sessions/{id}/submit` → runs **example + hidden tests**; the client
  gets aggregate hidden pass counts only (hidden inputs are never returned).
- Results are stored on the session and folded into the interview grade so the
  score reflects real correctness.

## Notes
- On Apple Silicon Piston runs under emulation (works, slightly slower).
- Runtimes persist in the `piston-packages` Docker volume, so you only run
  `install-runtimes.sh` once.
- No network is available to executed code; time/memory are limited by Piston.

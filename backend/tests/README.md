# Interview-quality tests

Automated tests that verify the AI interviewer actually behaves like a
world-class system-design interviewer — so you don't have to run a live
interview every time to check quality.

## Run

```bash
cd backend
source .venv/bin/activate
pytest                    # all tests
pytest -k lld             # just the low-level-design drill-down tests
pytest -k "not requires"  # (not needed) — see below
```

The **live-model tests call your configured LLM** (Azure/OpenAI) and assert on
observable behavior. They automatically **skip when no LLM key is configured**,
so the suite stays green in CI without credentials (only the fast pure-logic
tests run).

Expect the full suite to take ~1 minute (real model calls).

## What's covered

**`test_interviewer_behavior.py`** (live model)
- URL shortener → the interviewer drills into **unique code generation** and the
  **DB schema** (the low-level details).
- Challenges a **single point of failure / bottleneck**.
- Pushes for **capacity numbers** when the candidate hand-waves "millions of users".
- Probes **technology-choice justification** (e.g. "why Cassandra?").
- Follow-ups are **grounded in the candidate's actual answer**.

**`test_diagram_intelligence.py`**
- Pure-logic: structured **diff** (added/removed components & edges), graph→text.
- Live: architecture analysis **flags SPOFs/missing pieces**; the interviewer
  **stays silent on no-op diagram changes** but **reacts to significant ones**.

**`test_evaluation.py`** (live model)
- Design interviews produce the **full 14-dimension rubric** with
  **"how a strong candidate reasons"** teaching feedback.
- Coding interviews use the simpler 4-dimension rubric (not the design one).

## Notes
- Assertions check **concept coverage** (keyword/semantic variants across a short
  simulated conversation), not exact strings, since LLM wording varies.
- If a test fails, the failure message prints the interviewer's actual replies so
  you can see whether it's a real regression or just new phrasing to allow.

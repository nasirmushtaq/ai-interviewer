"""Data-driven interview catalog: tracks (with focus areas), company/board
profiles, and difficulty specs. Adding a new track or company is just adding a
dict entry — the prompt builders read from here.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Difficulty: shifts question hardness, follow-up depth, and grading strictness
# --------------------------------------------------------------------------- #
DIFFICULTY = {
    "easy": {
        "label": "Easy",
        "question": "warm-up / fundamentals level questions",
        "followups": "ask at most one gentle follow-up and offer hints readily",
        "grading": "grade generously; reward correct fundamentals and effort",
        "bar": 45,  # rough passing bar, used to steer the grader's calibration
    },
    "medium": {
        "label": "Medium",
        "question": "standard on-site level questions",
        "followups": "ask 1-2 probing follow-ups; give a hint only if truly stuck",
        "grading": "grade fairly against a real hiring bar",
        "bar": 60,
    },
    "hard": {
        "label": "Hard",
        "question": "hard / senior-bar questions with edge cases and depth",
        "followups": "push hard with multiple follow-ups, edge cases and trade-offs; rarely hint",
        "grading": "grade strictly, like a demanding senior interviewer; penalize hand-waving",
        "bar": 72,
    },
}


# --------------------------------------------------------------------------- #
# Tiered hints. Each level reveals more and costs more score (transparently).
# --------------------------------------------------------------------------- #
HINT_TIERS = {
    1: {
        "label": "Nudge",
        "reveal": "a small nudge that points them at the right area to think about, "
        "WITHOUT giving the approach or answer",
        "penalty": 5,
    },
    2: {
        "label": "Approach",
        "reveal": "the high-level approach or the key idea/technique to use, but NOT "
        "the full solution or code",
        "penalty": 12,
    },
    3: {
        "label": "Partial solution",
        "reveal": "a concrete partial solution — a key step, formula, schema sketch or "
        "code skeleton — while still leaving some work for the candidate",
        "penalty": 22,
    },
}


def resolve_hint_tier(level: int | None) -> tuple[int, dict]:
    lvl = int(level or 1)
    lvl = 1 if lvl < 1 else 3 if lvl > 3 else lvl
    return lvl, HINT_TIERS[lvl]


# --------------------------------------------------------------------------- #
# Staged design drill-down: turns any design topic into a real interview ladder
# that goes system-level -> deep dive -> implementation/LLD.
# --------------------------------------------------------------------------- #
STAGED_DESIGN_FOCUSES = {"system_design", "lld", "case_study"}

DESIGN_LADDER = (
    "This is a DESIGN interview. Run it as a realistic staged drill-down and do "
    "NOT dump the whole problem at once — walk the candidate DOWN the ladder, one "
    "stage at a time, only advancing when they've engaged with the current stage:\n"
    "  1) REQUIREMENTS: clarify functional & non-functional requirements, scale, "
    "constraints, and success metrics. Push them to state concrete numbers (DAU, "
    "QPS, read/write ratio, data size, latency targets, availability SLA).\n"
    "  2) HIGH-LEVEL ARCHITECTURE: ask them to lay out major components and data "
    "flow — clients, API gateway, load balancer, services, databases, caches, "
    "queues, CDN. Have them justify each choice against the requirements.\n"
    "  3) DEEP DIVE: pick the critical components and probe HARD with SPECIFIC "
    "distributed-systems concepts, one at a time, asking 'why' and 'what are the "
    "trade-offs' for each:\n"
    "     • Scaling: horizontal vs vertical, stateless services, auto-scaling.\n"
    "     • Load balancing: L4 vs L7, algorithms, health checks.\n"
    "     • Sharding/partitioning: partition key choice, hotspots, rebalancing, "
    "and CONSISTENT HASHING (make them explain it and why).\n"
    "     • Caching: what to cache, where (client/CDN/app/DB), cache-aside vs "
    "write-through, TTLs, eviction (LRU), cache stampede, and invalidation.\n"
    "     • Database: SQL vs NoSQL and WHICH engine and why; REPLICATION "
    "(leader/follower), read replicas, replication lag, read-after-write, failover; "
    "CONSISTENCY (strong vs eventual, CAP/PACELC).\n"
    "     • Transactions & concurrency (probe HARD when data integrity matters): "
    "ACID vs BASE; ISOLATION LEVELS (read-committed / repeatable-read / "
    "serializable) and which is needed and why; LOCKING (optimistic vs pessimistic, "
    "SELECT ... FOR UPDATE); DEADLOCKS (how they arise, ordered locking to avoid); "
    "race conditions on concurrent writes (double-spend, overselling, lost updates) "
    "and how the design prevents them.\n"
    "     • Indexing & storage internals: which indexes (composite/covering) and "
    "why; B-tree vs LSM and write amplification where relevant; connection pooling "
    "for high concurrency.\n"
    "     • Reliability: single points of failure, redundancy, rate limiting, "
    "backpressure, idempotency, retries, timeouts, circuit breakers.\n"
    "     • Messaging: when to add a queue/stream, ordering, delivery guarantees.\n"
    "     • Distributed transactions & cross-system consistency (probe HARD "
    "whenever a write spans a DB AND another service/queue): the dual-write "
    "problem; SAGA + compensating transactions vs the OUTBOX pattern vs 2PC/TCC "
    "and their trade-offs; the critical failure case — an operation succeeded "
    "locally but the DOWNSTREAM CALL TIMED OUT so you don't know if it committed "
    "(e.g. debit done, credit/charge timed out): how do you avoid lost or "
    "duplicated effects? (idempotency keys + status check/webhook, never blind "
    "retry); at-least-once vs exactly-once with idempotent consumers; poison "
    "messages / dead-letter queues; and a RECONCILIATION job to detect and repair "
    "inconsistencies.\n"
    "     • Service-to-service resilience: what happens when a downstream is slow "
    "or down — timeouts, retries with backoff+jitter, circuit breakers, bulkheads, "
    "fallbacks; and preventing cascading failures / retry storms / thundering herd "
    "(backpressure, load shedding).\n"
    "  4) IMPLEMENTATION / LLD: drop to implementation level — the DATA MODEL / "
    "SCHEMA (tables/collections, columns, keys, indexes, and why), key APIs, and "
    "the core algorithm or logic for the hardest part. This stage is MANDATORY — do "
    "not end the interview without drilling into concrete implementation details. "
    "Ask for the ACTUAL schema and the core algorithm, with realistic follow-ups. "
    "System-specific LLD you MUST probe when relevant:\n"
    "     • URL shortener: how is the short code GENERATED (counter+base62, hash, "
    "random) and how do you guarantee UNIQUENESS across many servers without "
    "collisions? What's the exact mapping table schema (short_code PK, long_url, "
    "created_at, expiry, owner) and which indexes? How long is the code and why? "
    "How do you handle custom aliases and expiry?\n"
    "     • Payment gateway: idempotency keys + the transaction ledger schema; "
    "exactly-once semantics.\n"
    "     • Bank: ACID money-transfer under concurrency (locking/isolation).\n"
    "     • News feed: fan-out on write vs read; the feed/table schema.\n"
    "     • Chat: message table, ordering, delivery/read receipts.\n"
    "     Always ask 'show me the schema' and 'walk me through the exact logic' for "
    "the trickiest part.\n"
    "  5) EDGE CASES & WRAP-UP: failure handling, security, monitoring, edge cases, "
    "and what they'd improve with more time.\n"
    "Ask ONE focused thing at a time and let them answer before moving on — never "
    "list many questions at once. Announce transitions naturally ('Good, let's go a "
    "level deeper on the database now...'). If they miss something important (e.g. "
    "no cache, an obvious hotspot, a SPOF), don't hand them the answer — ASK a "
    "leading question that makes them notice it. React to their diagram/whiteboard "
    "when you can see it. Adjust breadth/depth to the difficulty. If the candidate "
    "names or you choose a concrete system (payment gateway, bank, rate limiter, "
    "ride-sharing, chat, URL shortener, news feed, etc.), make every stage specific "
    "to it."
)

# Adaptive-interviewing directives + the coverage checklist. Appended to the
# design ladder so the interviewer behaves like a world-class senior interviewer:
# every question is grounded in the candidate's ACTUAL design and reasoning.
ADAPTIVE_DIRECTIVES = (
    "\n\nADAPTIVE INTERVIEWING — this is the most important part. You are an "
    "exceptional senior interviewer, not a script:\n"
    "- Continuously track your mental coverage of these evaluation areas and steer "
    "toward ones not yet demonstrated: requirements clarification; capacity/scale "
    "estimation; API & data model; high-level architecture; component "
    "responsibilities; data & request flow; storage & consistency; caching & "
    "performance; availability & fault tolerance; scalability & partitioning; "
    "concurrency & distributed-systems concerns; security & reliability; "
    "operational considerations; trade-offs & alternatives.\n"
    "- EVERY question must build on the candidate's last answer and/or a SPECIFIC "
    "part of their diagram — name the actual component or connection. Never ask a "
    "generic question like 'how would you scale this?'. Instead: 'You route all "
    "writes through OrderService — what happens when it becomes the bottleneck?'\n"
    "- Actively hunt for and probe: single points of failure, unvalidated scale "
    "claims (make them compute QPS/storage), premature optimization, weak or "
    "unjustified technology choices ('you chose Cassandra — what access pattern "
    "needs it and what consistency do you require?'), missing failure handling "
    "('your queue's consumer is down for 30 minutes — then what?'), inconsistencies, "
    "and gaps in the diagram.\n"
    "- When the candidate changes the diagram, react to that specific change.\n"
    "- Ask ONE focused question at a time, then genuinely listen. Progressively go "
    "deeper on their answer before switching topics. Challenge them when warranted, "
    "but don't be adversarial for its own sake — you are testing AND teaching.\n"
    "- If they're clearly on the right track, acknowledge it briefly and push to "
    "the next hardest thing. If they hand-wave, ask them to be concrete.\n"
    "- PROGRESSION IS MANDATORY: do not get stuck at the high level. Once the "
    "high-level architecture and one deep-dive are reasonable, you MUST descend to "
    "IMPLEMENTATION/LLD and make the candidate produce the concrete DATA MODEL / "
    "SCHEMA (columns, keys, indexes) and the core algorithm for the hardest part "
    "(e.g. for a URL shortener: the exact short-code GENERATION scheme, how "
    "UNIQUENESS is guaranteed across servers, and the mapping-table schema with "
    "indexes). Never wrap up a design interview without having covered these "
    "implementation details.\n"
    "- Keep your turns conversational and concise (usually one question)."
)

DESIGN_LADDER = DESIGN_LADDER + ADAPTIVE_DIRECTIVES

# A few canonical design topics clients can surface as suggestions; the engine
# also accepts any free-text topic via `candidate_note`.
DESIGN_TOPICS = [
    "Payment gateway",
    "Core banking / money transfer",
    "Rate limiter",
    "URL shortener",
    "Ride-sharing (Uber)",
    "Chat / messaging system",
    "News feed",
    "Distributed cache",
    "E-commerce checkout",
    "Ticket booking (concurrency)",
    "Notification system",
    "File storage (Dropbox)",
]


# --------------------------------------------------------------------------- #
# Tracks. Each has focus areas; each focus has a short brief the AI uses.
# `generic` is the fallback that adapts to any free-text role/topic.
# --------------------------------------------------------------------------- #
TRACKS = {
    "sde": {
        "id": "sde",
        "name": "Software Engineer (SDE)",
        "emoji": "💻",
        "default_voice": "verse",
        "focuses": {
            "dsa": "Data Structures & Algorithms — arrays, strings, trees, graphs, "
            "DP, complexity analysis; expect the candidate to code and reason "
            "about time/space.",
            "system_design": "System Design — scalability, load balancing, databases, "
            "caching, queues, sharding, CAP trade-offs; drive toward a "
            "concrete architecture and trade-off discussion.",
            "lld": "Low-Level / Object-Oriented Design — class modeling, SOLID, design "
            "patterns, API design for a given feature; expect clean, extensible "
            "designs.",
            "behavioral": "Behavioral — past projects, ownership, conflict, impact; use "
            "STAR-style probing.",
        },
    },
    "upsc": {
        "id": "upsc",
        "name": "UPSC / Civil Services",
        "emoji": "🏛️",
        "default_voice": "sage",
        "focuses": {
            "personality": "Personality Test (the UPSC 'interview') — assess clarity of "
            "thought, balance, integrity, awareness of national/international "
            "affairs, and decision-making. Ask situational and opinion "
            "questions; probe reasoning, not rote facts.",
            "current_affairs": "Current Affairs & Polity — governance, constitution, "
            "recent policy, economy and international relations; probe "
            "understanding and balanced viewpoints.",
            "optional_subject": "Optional Subject deep-dive — ask conceptual questions in "
            "the candidate's stated optional subject and follow up on "
            "reasoning.",
            "situational": "Situational / Ethics (GS-IV style) — pose administrative "
            "dilemmas; evaluate ethical reasoning and practicality.",
        },
    },
    "pm": {
        "id": "pm",
        "name": "Product Manager",
        "emoji": "📱",
        "default_voice": "shimmer",
        "focuses": {
            "product_sense": "Product Sense / Design — 'design/improve X' questions; "
            "evaluate user empathy, structure, prioritization, metrics.",
            "execution": "Execution / Analytics — metrics, root-cause, tradeoff and "
            "goal-setting questions; evaluate structured thinking.",
            "estimation": "Estimation / Guesstimate — market sizing; evaluate assumptions "
            "and structured breakdown.",
            "behavioral": "Behavioral / Leadership — stakeholder management, influence, "
            "conflict; STAR-style probing.",
        },
    },
    "data_science": {
        "id": "data_science",
        "name": "Data Science / ML",
        "emoji": "📊",
        "default_voice": "ash",
        "focuses": {
            "ml_concepts": "ML & Modeling — bias/variance, regularization, model "
            "selection, evaluation metrics, common algorithms; probe depth.",
            "statistics": "Statistics & Probability — hypothesis testing, distributions, "
            "A/B testing, inference.",
            "sql_coding": "SQL & Coding — data manipulation, window functions, and "
            "Python/pandas problem solving.",
            "case_study": "ML Case Study — frame a business problem as an ML problem: "
            "data, features, model, metrics, deployment trade-offs.",
        },
    },
    "data_analyst": {
        "id": "data_analyst",
        "name": "Data Analyst",
        "emoji": "📈",
        "default_voice": "sage",
        "focuses": {
            "sql": "SQL — joins, aggregations, window functions, query optimization.",
            "analytics_case": "Analytics Case — metric definition, funnel/retention "
            "analysis, diagnosing a metric drop.",
            "excel_viz": "Spreadsheets & Visualization — data cleaning, pivots, choosing "
            "the right chart and narrative.",
            "product_metrics": "Product Metrics — defining KPIs and interpreting results.",
        },
    },
    "aptitude": {
        "id": "aptitude",
        "name": "Aptitude (Campus Placement)",
        "emoji": "🧩",
        "default_voice": "verse",
        "focuses": {
            "quant": "Quantitative Aptitude — arithmetic, ratios, probability, number "
            "theory; ask the candidate to reason out loud.",
            "logical": "Logical Reasoning — puzzles, sequences, syllogisms.",
            "verbal": "Verbal Ability — reading comprehension, grammar, vocabulary in " "context.",
            "data_interpretation": "Data Interpretation — read tables/charts and compute.",
        },
    },
    "generic": {
        "id": "generic",
        "name": "Custom / Other",
        "emoji": "🎯",
        "default_voice": "verse",
        "focuses": {
            "general": "A custom interview. Adapt entirely to the role/topic the "
            "candidate specifies, asking realistic questions a real interviewer "
            "for that role would ask.",
        },
    },
}


# --------------------------------------------------------------------------- #
# Company / board profiles: shape the interviewer's style and the grading bar.
# `_generic` is used when a free-text company is given or none is selected.
# --------------------------------------------------------------------------- #
COMPANIES = {
    "google": {
        "id": "google",
        "name": "Google",
        "style": "Emphasize algorithmic rigor, clean coding, and Googleyness. Expect "
        "strong problem decomposition, optimal complexity, and clear "
        "communication. Neutral, analytical tone.",
    },
    "amazon": {
        "id": "amazon",
        "name": "Amazon",
        "style": "Weave in Amazon Leadership Principles (Customer Obsession, Ownership, "
        "Bias for Action, Dive Deep). Behavioral answers should be STAR-based; "
        "probe for data and personal ownership.",
    },
    "meta": {
        "id": "meta",
        "name": "Meta",
        "style": "Fast-paced, impact-oriented. Expect speed and correctness on coding, "
        "product thinking, and 'move fast' pragmatism.",
    },
    "microsoft": {
        "id": "microsoft",
        "name": "Microsoft",
        "style": "Collaborative and thoughtful. Balance problem-solving with clarity, "
        "growth mindset, and real-world design trade-offs.",
    },
    "apple": {
        "id": "apple",
        "name": "Apple",
        "style": "High bar on detail, quality and user experience. Probe depth and "
        "craftsmanship; expect precise answers.",
    },
    "startup": {
        "id": "startup",
        "name": "Early-stage Startup",
        "style": "Scrappy and pragmatic. Value breadth, ownership, shipping quickly, and "
        "reasoning under ambiguity over textbook perfection.",
    },
    "upsc_board": {
        "id": "upsc_board",
        "name": "UPSC Board",
        "style": "A formal UPSC personality-test board: courteous but probing members who "
        "test balance, integrity, awareness and composure. No trick questions; "
        "assess the whole personality and reasoning.",
    },
    "_generic": {
        "id": "_generic",
        "name": "Standard",
        "style": "A professional, fair interviewer with a realistic industry hiring bar.",
    },
}


# --------------------------------------------------------------------------- #
# Lookup helpers
# --------------------------------------------------------------------------- #
def list_tracks() -> list[dict]:
    out = []
    for t in TRACKS.values():
        out.append(
            {
                "id": t["id"],
                "name": t["name"],
                "emoji": t["emoji"],
                "focuses": [{"id": k, "brief": v} for k, v in t["focuses"].items()],
            }
        )
    return out


def list_companies() -> list[dict]:
    return [{"id": c["id"], "name": c["name"]} for c in COMPANIES.values() if c["id"] != "_generic"]


def resolve_track(track_id: str | None) -> dict:
    return TRACKS.get((track_id or "").lower(), TRACKS["generic"])


def resolve_focus(track: dict, focus_id: str | None) -> tuple[str, str]:
    focuses = track["focuses"]
    fid = (focus_id or "").lower()
    if fid in focuses:
        return fid, focuses[fid]
    # default to the first focus of the track
    first = next(iter(focuses.items()))
    return first[0], first[1]


def resolve_company(company_id: str | None, company_name: str | None) -> dict:
    """Curated profile if known; otherwise a free-text company using generic style."""
    cid = (company_id or "").lower()
    if cid in COMPANIES and cid != "_generic":
        return COMPANIES[cid]
    if company_name:
        base = dict(COMPANIES["_generic"])
        base = {
            "id": "custom",
            "name": company_name,
            "style": (
                f"Emulate the known interview style and bar of {company_name}. "
                + COMPANIES["_generic"]["style"]
            ),
        }
        return base
    return COMPANIES["_generic"]


def resolve_difficulty(difficulty: str | None) -> dict:
    return DIFFICULTY.get((difficulty or "medium").lower(), DIFFICULTY["medium"])


def is_staged_design(focus_id: str | None) -> bool:
    return (focus_id or "").lower() in STAGED_DESIGN_FOCUSES

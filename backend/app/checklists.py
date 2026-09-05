"""Coverage checklists — the definition of a COMPREHENSIVE interview.

Each system-design problem has a set of MUST-HIT items grouped by area. The
interview is not allowed to conclude until every mandatory item is covered. A
generic checklist (the 14 evaluation areas with standard sub-topics) applies to
any system not specifically listed.

Item statuses tracked per session: not_asked | asked | answered_weak |
answered_strong.
"""

# Generic system-design checklist — applies to ANY design problem.
GENERIC_CHECKLIST = {
    "requirements": [
        "functional requirements clarified",
        "non-functional requirements (latency, availability, consistency) clarified",
    ],
    "estimation": [
        "traffic/QPS estimated with numbers",
        "storage growth estimated with numbers",
    ],
    "api_data_model": [
        "core APIs defined",
        "data model / schema defined (tables, keys, indexes)",
    ],
    "high_level_architecture": [
        "major components and their responsibilities laid out",
        "request/data flow through the system explained",
    ],
    "storage_consistency": [
        "datastore choice justified by access pattern",
        "SQL vs NoSQL decision (which engine and WHY)",
        "consistency model (strong vs eventual) chosen and justified",
        "replication (leader/follower), replication lag, read-after-write handled",
    ],
    "transactions_concurrency": [
        "transactions / ACID vs BASE where data integrity matters",
        "isolation level chosen (read-committed / repeatable-read / serializable) and why",
        "locking strategy (optimistic vs pessimistic) for contended writes",
        "deadlocks: how they arise and how to avoid/handle them",
        "race conditions on concurrent writes handled (e.g. double-spend, oversell)",
    ],
    "indexing_storage_internals": [
        "indexing strategy (which columns, composite/covering) and why",
        "index/storage internals impact (B-tree vs LSM, write amplification) where relevant",
        "connection pooling / handling many concurrent connections",
    ],
    "distributed_transactions": [
        "cross-system writes: dual-write problem identified (DB + message/other service)",
        "consistency across services (saga + compensation, outbox pattern, or 2PC) chosen and justified",
        "the 'action succeeded but the downstream call timed out — did it commit?' ambiguity handled",
        "at-least-once vs exactly-once, with idempotent consumers to dedupe retries",
        "partial-failure recovery: retries, poison messages / dead-letter queue, reconciliation job",
        "event ordering / delivery guarantees where events drive state",
    ],
    "service_resilience": [
        "downstream slow/unavailable handling: timeouts, retries with backoff+jitter",
        "circuit breakers / bulkheads / fallbacks to contain failures",
        "cascading failure and retry-storm / thundering-herd prevention (backpressure, load shedding)",
    ],
    "caching_performance": [
        "caching strategy (what/where/how) defined",
        "cache invalidation / staleness handled",
    ],
    "availability_fault_tolerance": [
        "single points of failure identified and mitigated",
        "failure scenarios and recovery discussed",
    ],
    "scalability_partitioning": [
        "horizontal scaling / statelessness addressed",
        "partitioning/sharding strategy (partition key, rebalancing) defined",
    ],
    "concurrency_distributed": [
        "concurrency / race conditions addressed where relevant",
        "distributed-systems concern (ordering, idempotency, coordination) addressed",
    ],
    "security_reliability": [
        "security concerns (auth, abuse, rate limiting) addressed",
    ],
    "operations": [
        "monitoring/observability or operational concerns mentioned",
    ],
    "tradeoffs": [
        "key trade-offs and alternatives discussed",
    ],
}

# Per-topic ADDITIONS/overrides — the specific things that make an interview on
# THIS system comprehensive. Merged on top of the generic checklist.
TOPIC_CHECKLISTS = {
    "url_shortener": {
        "keywords": ["url shorten", "tinyurl", "bit.ly", "short link", "shorten"],
        "extra": {
            "core_algorithm": [
                "short-code generation scheme (counter+base62 / hash / random)",
                "uniqueness guaranteed across servers without collisions",
                "code length chosen and justified",
            ],
            "api_data_model": [
                "mapping table schema (short_code PK, long_url, created_at, expiry, owner)",
                "custom alias handling and collisions",
                "expiry / TTL handling",
            ],
            "caching_performance": [
                "hot-link caching and redirect latency",
            ],
        },
    },
    "rate_limiter": {
        "keywords": ["rate limit", "throttl", "rate-limit"],
        "extra": {
            "core_algorithm": [
                "algorithm chosen (token bucket / leaky bucket / sliding window)",
                "per-user vs global limits",
                "distributed counter / shared state (Redis) and atomicity",
            ],
            "availability_fault_tolerance": [
                "behavior when the limiter store is down (fail open vs closed)",
            ],
        },
    },
    "news_feed": {
        "keywords": ["news feed", "newsfeed", "timeline", "social feed", "feed"],
        "extra": {
            "core_algorithm": [
                "fan-out on write vs fan-out on read chosen and justified",
                "celebrity / hot-user problem handled",
                "feed ranking / ordering approach",
            ],
            "api_data_model": [
                "feed and posts schema",
            ],
        },
    },
    "chat": {
        "keywords": ["chat", "messaging", "whatsapp", "slack", "instant messag"],
        "extra": {
            "core_algorithm": [
                "message delivery (push vs pull, websockets/long-poll)",
                "ordering and delivery/read receipts",
                "online presence handling",
            ],
            "api_data_model": [
                "message and conversation schema",
            ],
        },
    },
    "payment_gateway": {
        "keywords": ["payment gateway", "payment", "checkout", "billing system"],
        "extra": {
            "core_algorithm": [
                "idempotency keys to prevent double charges",
                "transaction ledger / double-entry approach",
                "exactly-once / reconciliation on failures",
            ],
            "transactions_concurrency": [
                "serializable/repeatable-read isolation for money movement and why",
                "pessimistic locking or SELECT ... FOR UPDATE on balances",
                "preventing double-spend under concurrent debits",
            ],
            "distributed_transactions": [
                "calling an external processor (Stripe/bank) that may time out — did the charge go through? (idempotency key + status polling/webhook, never blind retry)",
                "saga/outbox to keep our DB and the external charge consistent",
            ],
            "security_reliability": [
                "PCI / sensitive data handling",
            ],
        },
    },
    "ticketing": {
        "keywords": [
            "ticket booking",
            "seat booking",
            "reservation",
            "inventory",
            "flash sale",
            "e-commerce checkout",
            "oversell",
        ],
        "extra": {
            "transactions_concurrency": [
                "prevent overselling the same seat/item under high concurrency",
                "optimistic (version/CAS) vs pessimistic locking for inventory",
                "hold/reserve then confirm flow with timeouts",
                "isolation level to avoid lost updates",
            ],
        },
    },
    "bank": {
        "keywords": ["bank", "ledger", "money transfer", "core banking", "wallet"],
        "extra": {
            "transactions_concurrency": [
                "ACID money-transfer: debit+credit atomic in one transaction",
                "isolation level (serializable) and locking to prevent double-spend",
                "deadlock avoidance when locking two accounts (ordered locking)",
                "idempotency for retried transfers",
            ],
            "distributed_transactions": [
                "cross-bank/external transfer where debit and credit span systems",
                "timeout mid-transfer: debit sent but downstream credit timed out — how to avoid lost/duplicate money (outbox + idempotent retry, or saga with compensation/reversal)",
                "reconciliation to detect and repair stuck/inconsistent transfers",
            ],
            "api_data_model": [
                "accounts + ledger/entries schema (immutable append)",
            ],
        },
    },
}


def detect_topic(text: str) -> str | None:
    """Best-effort detect the concrete system from the opening/context text."""
    t = (text or "").lower()
    for topic_id, spec in TOPIC_CHECKLISTS.items():
        if any(k in t for k in spec["keywords"]):
            return topic_id
    return None


def build_checklist(topic_id: str | None) -> dict:
    """Merge the generic checklist with any topic-specific additions, returning
    {area: [items]}."""
    import copy

    checklist = copy.deepcopy(GENERIC_CHECKLIST)
    if topic_id and topic_id in TOPIC_CHECKLISTS:
        for area, items in TOPIC_CHECKLISTS[topic_id]["extra"].items():
            checklist.setdefault(area, [])
            for it in items:
                if it not in checklist[area]:
                    checklist[area].append(it)
    return checklist


def init_coverage(topic_id: str | None) -> dict:
    """Fresh coverage state: every item starts 'not_asked'."""
    checklist = build_checklist(topic_id)
    items = []
    for area, area_items in checklist.items():
        for it in area_items:
            items.append({"area": area, "item": it, "status": "not_asked"})
    return {"topic": topic_id, "items": items}


def all_items(coverage: dict) -> list[dict]:
    return (coverage or {}).get("items", [])


def open_items(coverage: dict) -> list[dict]:
    """Items not yet adequately covered (not_asked or answered_weak)."""
    return [i for i in all_items(coverage) if i.get("status") in ("not_asked", "answered_weak")]


def is_complete(coverage: dict) -> bool:
    """Complete when no mandatory item is still not_asked. (answered_weak is
    allowed to end — the candidate was asked but did poorly; that's graded.)"""
    return not any(i.get("status") == "not_asked" for i in all_items(coverage))


def coverage_summary(coverage: dict) -> dict:
    items = all_items(coverage)
    from collections import Counter

    c = Counter(i.get("status", "not_asked") for i in items)
    return {
        "total": len(items),
        "not_asked": c.get("not_asked", 0),
        "asked": c.get("asked", 0),
        "answered_weak": c.get("answered_weak", 0),
        "answered_strong": c.get("answered_strong", 0),
        "complete": is_complete(coverage),
    }


def next_targets(coverage: dict, n: int = 3) -> list[dict]:
    """Highest-priority items to attack next: not_asked first, then weak."""
    items = all_items(coverage)
    not_asked = [i for i in items if i.get("status") == "not_asked"]
    weak = [i for i in items if i.get("status") == "answered_weak"]
    return (not_asked + weak)[:n]

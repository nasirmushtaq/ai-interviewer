"""Interview-quality tests: does the interviewer actually probe the things a
world-class system-design interviewer should? These call the real model.

Run:  pytest tests/ -q            (skips if no LLM key)
      pytest tests/ -q -k lld     (just the drill-down tests)
"""
from conftest import Interviewer, requires_llm, covers_any


@requires_llm
def test_url_shortener_drills_into_unique_code_generation():
    """A candidate who stays high-level should still be pushed to explain how
    short codes are generated and kept unique across servers. Over a few turns
    of a real interview, uniqueness/code-generation should come up."""
    iv = Interviewer(seed_history=[
        {"role": "assistant", "text": "Thanks for the intro. Design a URL shortener. ~100M new URLs/day, 10:1 read/write, p99<50ms."},
        {"role": "user", "text": "Client -> LB -> app servers -> a service storing code->url in the DB, plus a Redis cache for hot reads. I'd scale app servers horizontally."},
        {"role": "assistant", "text": "Good shape. What's the biggest risk?"},
        {"role": "user", "text": "The DB. I'd add read replicas and shard by short code."},
    ])
    # Answer whatever it asks, briefly, a few times — uniqueness/code-gen is a
    # core part of this problem and should surface within a normal interview.
    iv.say("I'd route by hashing the code to a shard; resharding I'd handle with consistent hashing.")
    iv.say("Consistent hashing keeps relocation minimal.")
    iv.say("Okay, I think the sharding and caching are solid.")
    iv.say("What else should we cover?")
    text = iv.interviewer_text()
    assert covers_any(text, [
        "unique", "uniqueness", "collision", "generate the short code",
        "code generation", "short code", "base62", "counter", "id generation",
        "generate the code", "how are the codes", "how do you create",
    ]), f"Interviewer never probed unique code generation.\n---\n{text}"


@requires_llm
def test_url_shortener_asks_for_db_schema():
    """The interviewer must reach the concrete data model / schema before wrapping."""
    iv = Interviewer(seed_history=[
        {"role": "assistant", "text": "We covered code generation and uniqueness (counter + base62 with range allocation)."},
        {"role": "user", "text": "Right, counter + base62 via a range-allocation service."},
    ])
    iv.say("I think the design is complete, should we wrap up?")
    iv.say("Okay, anything else?")
    text = iv.interviewer_text()
    assert covers_any(text, [
        "schema", "table", "columns", "primary key", "index",
        "data model", "mapping table",
    ]), f"Interviewer never asked for the DB schema.\n---\n{text}"


@requires_llm
def test_probes_single_point_of_failure():
    """When all traffic funnels through one component, it should be challenged."""
    iv = Interviewer(seed_history=[
        {"role": "assistant", "text": "Thanks for the intro. Let's design an order system. Walk me through your architecture."},
        {"role": "user", "text": "Sure, let me sketch the high-level design."},
    ])
    iv.say("Every write goes through a single OrderService, which writes to one Postgres instance. We expect millions of users.")
    text = iv.interviewer_text()
    assert covers_any(text, [
        "bottleneck", "single point of failure", "spof", "fail", "failover",
        "replica", "replication", "what happens when", "single write path",
        "single point", "centralized", "single write", "viable", "one postgres",
    ]), f"Interviewer didn't challenge the SPOF/bottleneck.\n---\n{text}"


@requires_llm
def test_challenges_unvalidated_scale_claim():
    """'Millions of users' with no numbers should prompt capacity estimation."""
    iv = Interviewer(seed_history=[
        {"role": "assistant", "text": "Thanks for the intro. Let's begin the design. What are we building's requirements?"},
        {"role": "user", "text": "A general purpose backend."},
    ])
    iv.say("It will serve millions of users and be super fast.")
    text = iv.interviewer_text()
    assert covers_any(text, [
        "qps", "requests per second", "throughput", "how many", "estimate",
        "storage", "traffic", "numbers", "capacity", "read/write",
    ]), f"Interviewer didn't push for capacity numbers.\n---\n{text}"


@requires_llm
def test_probes_technology_choice_justification():
    """Picking a datastore should trigger 'why / what access pattern' probing."""
    iv = Interviewer(seed_history=[
        {"role": "assistant", "text": "Thanks for the intro. Let's design a product catalog. What's your high-level plan?"},
        {"role": "user", "text": "I'll have an API layer and a datastore."},
        {"role": "assistant", "text": "Okay, let's talk about that datastore."},
    ])
    iv.say("I'll use Cassandra for everything.")
    text = iv.interviewer_text()
    assert covers_any(text, [
        "why", "access pattern", "consistency", "trade-off", "tradeoff",
        "what makes", "justif", "instead of",
    ]), f"Interviewer didn't probe the Cassandra choice.\n---\n{text}"


@requires_llm
def test_adaptive_followup_references_candidate_answer():
    """The next question should build on what the candidate actually said."""
    iv = Interviewer(seed_history=[
        {"role": "assistant", "text": "Thanks for the intro. Let's design a chat system. Walk me through your approach."},
        {"role": "user", "text": "I'll start with the message delivery path."},
    ])
    reply = iv.say("I'd put a Kafka queue between the message service and the delivery workers.")
    r = reply.lower()
    assert covers_any(r, [
        "queue", "kafka", "consumer", "worker", "delivery", "message",
        "down", "lag", "ordering", "backpressure",
    ]), f"Follow-up wasn't grounded in the candidate's answer.\n---\n{reply}"


@requires_llm
def test_drills_into_db_transactions_and_locking():
    """A transactional system with a shallow DB answer should be pushed into
    transactions / isolation / locking (deep DB internals)."""
    iv = Interviewer(seed_history=[
        {"role": "assistant", "text": "Thanks for the intro. Design a bank money-transfer between accounts."},
        {"role": "user", "text": "Accounts table + a transfers API; subtract from one account, add to the other in the DB."},
    ])
    iv.say("For concurrency I'll just be careful.")
    iv.say("I think that handles it.")
    text = iv.interviewer_text()
    assert covers_any(text, [
        "transaction", "isolation", "lock", "acid", "double-spend",
        "lost update", "serializable", "for update", "concurrent",
    ]), f"Interviewer didn't drill DB transactions/locking.\n---\n{text}"


@requires_llm
def test_probes_timeout_debit_distributed_failure():
    """A local-debit + remote-credit design should trigger the classic 'debit
    committed but downstream credit timed out' distributed-failure probe."""
    iv = Interviewer(seed_history=[
        {"role": "assistant", "text": "Thanks for the intro. Design money transfer where the payee lives in a different service."},
        {"role": "user", "text": "I debit the sender in my DB, then call the Payee service API to credit the receiver."},
        {"role": "assistant", "text": "So a local debit then a remote credit call."},
    ])
    iv.say("Yes, that completes the transfer.")
    text = iv.interviewer_text()
    assert covers_any(text, [
        "timed out", "timeout", "don't know whether", "did the credit",
        "credit twice", "duplicat", "lose money", "losing money",
        "saga", "outbox", "idempot", "compensat", "reconcil",
    ]), f"Interviewer didn't probe the timeout-debit distributed failure.\n---\n{text}"

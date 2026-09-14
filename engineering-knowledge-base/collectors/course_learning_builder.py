from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import re


@dataclass(frozen=True)
class TopicProfile:
    key: str
    role: str
    components: tuple[tuple[str, str], ...]
    flow: tuple[str, ...]
    implementation: tuple[str, ...]
    failures: tuple[str, ...]
    metrics: tuple[str, ...]
    security: tuple[str, ...]
    tradeoffs: tuple[str, ...]


PROFILES: tuple[tuple[tuple[str, ...], TopicProfile], ...] = (
    (
        ("docker", "environment", "repository", "development setup"),
        TopicProfile(
            "foundation",
            "Create a repeatable engineering baseline so later distributed components can be built, tested, and replaced without environment drift.",
            (
                ("Developer workspace", "Source code, tests, local configuration, and documentation."),
                ("Container runtime", "Reproducible process isolation and dependency packaging."),
                ("Version control", "Change history, collaboration, rollback, and review."),
                ("Local orchestration", "Starts dependencies and services with one deterministic command."),
            ),
            (
                "A developer changes a component in a versioned workspace.",
                "The component is built into an immutable runtime artifact.",
                "Local orchestration supplies configuration, networking, and dependencies.",
                "Smoke tests verify that the component starts and emits useful diagnostics.",
            ),
            (
                "Define a minimal repository layout with clear ownership boundaries.",
                "Pin runtime and dependency versions instead of relying on workstation defaults.",
                "Add one-command build, test, and start workflows.",
                "Create health checks and a sample event before introducing business complexity.",
            ),
            (
                "Environment-specific behavior caused by unpinned dependencies.",
                "Containers start but are not operational because readiness is not checked.",
                "Secrets or generated data are committed accidentally.",
            ),
            ("build duration", "startup time", "test pass rate", "container restart count"),
            ("keep secrets outside source control", "run containers with least privilege", "scan dependencies and images"),
            ("More tooling improves repeatability but increases setup complexity.", "A monorepo is simple initially but may require stronger boundaries later."),
        ),
    ),
    (
        ("tcp", "udp", "shipper", "network", "collector", "socket"),
        TopicProfile(
            "network-ingestion",
            "Move events from producers to the processing platform while balancing delivery reliability, latency, bandwidth, and backpressure.",
            (
                ("Producer or agent", "Reads local events and prepares transport batches."),
                ("Transport protocol", "Defines connection, framing, ordering, and delivery behavior."),
                ("Ingress listener", "Accepts traffic, validates envelopes, and applies admission control."),
                ("Durable handoff", "Separates network receipt from downstream processing."),
            ),
            (
                "The agent reads or receives a new event.",
                "Events are framed, optionally batched or compressed, and transmitted.",
                "The ingress listener authenticates the sender and validates limits.",
                "Accepted events are acknowledged only after the configured durability boundary.",
            ),
            (
                "Define an explicit event envelope with version, source, timestamp, and unique ID.",
                "Choose acknowledgement semantics before optimizing throughput.",
                "Bound connection counts, payload sizes, buffers, and retry delays.",
                "Add load tests that include slow consumers and network interruption.",
            ),
            (
                "Partial frames and malformed payloads exhaust parsing resources.",
                "Retries create duplicate events when acknowledgement state is ambiguous.",
                "Unbounded buffers move overload from the network into memory.",
            ),
            ("events per second", "ingress latency", "connection count", "retry rate", "dropped events", "buffer utilization"),
            ("mutual authentication where appropriate", "TLS in transit", "rate limits by tenant or source", "payload-size validation"),
            ("TCP favors ordered reliable delivery but has connection overhead.", "UDP reduces coordination cost but shifts loss detection and recovery to the application."),
        ),
    ),
    (
        ("json", "protobuf", "avro", "serialization", "schema", "normalization", "enrichment", "parsing"),
        TopicProfile(
            "data-contracts",
            "Turn heterogeneous event data into a governed, evolvable contract that downstream systems can process safely.",
            (
                ("Parser or decoder", "Transforms bytes or text into typed fields."),
                ("Canonical event model", "Stable internal representation used across the platform."),
                ("Schema registry", "Stores versions and compatibility rules."),
                ("Enrichment pipeline", "Adds trusted contextual metadata without mutating source facts."),
            ),
            (
                "Raw input is classified by format and schema version.",
                "The decoder validates syntax and required fields.",
                "Normalization maps source fields into the canonical model.",
                "Enrichment adds environment, ownership, and correlation context.",
                "Invalid records are quarantined with an explainable reason.",
            ),
            (
                "Separate parsing errors from business validation errors.",
                "Version schemas explicitly and define backward/forward compatibility policy.",
                "Preserve original event data or a checksum for audit and replay.",
                "Use contract tests between producers and consumers.",
            ),
            (
                "A producer deploys an incompatible field change.",
                "A permissive parser silently drops information.",
                "Enrichment calls external systems synchronously and stalls ingestion.",
            ),
            ("decode failures", "schema-version distribution", "quarantine rate", "enrichment latency", "payload size"),
            ("validate untrusted input", "redact sensitive values before broad distribution", "restrict schema changes through review"),
            ("Human-readable formats simplify debugging but cost bandwidth and CPU.", "Binary schemas improve efficiency but require stronger tooling and governance."),
        ),
    ),
    (
        ("storage", "partition", "replication", "consistent hashing", "quorum", "anti-entropy", "leader election", "cluster"),
        TopicProfile(
            "distributed-storage",
            "Store data across nodes while making placement, replication, consistency, repair, and failure recovery explicit.",
            (
                ("Partitioner", "Maps each record to a shard using a stable key."),
                ("Replica set", "Maintains redundant copies across failure domains."),
                ("Coordinator", "Routes operations and applies consistency policy."),
                ("Repair process", "Detects and reconciles divergent replicas."),
            ),
            (
                "A partition key is derived from the event and retention/query requirements.",
                "The coordinator selects replicas from the placement map.",
                "Writes are persisted according to the configured acknowledgement quorum.",
                "Reads reconcile versions when replicas disagree.",
                "Background repair limits long-lived divergence.",
            ),
            (
                "Choose partition keys from real access patterns, not only even distribution.",
                "Define replication factor and failure domains explicitly.",
                "Model read and write quorum behavior during partial failure.",
                "Test node replacement, rebalancing, and repair under load.",
            ),
            (
                "Hot partitions overload one subset of nodes.",
                "A network partition creates divergent replicas.",
                "Rebalancing competes with foreground traffic and increases latency.",
            ),
            ("read/write latency", "replica lag", "repair backlog", "hot-partition skew", "disk utilization", "rebalance duration"),
            ("encrypt data at rest", "authorize administrative operations", "audit replica and retention changes"),
            ("Stronger consistency increases coordination latency.", "More replicas improve durability but increase write cost and storage."),
        ),
    ),
    (
        ("rabbitmq", "kafka", "queue", "consumer", "producer", "dead letter", "stream", "exactly-once", "compaction"),
        TopicProfile(
            "messaging-streaming",
            "Decouple producers from processors through durable ordered delivery, explicit retry semantics, and scalable consumer coordination.",
            (
                ("Producer", "Publishes versioned events with stable identifiers."),
                ("Broker or log", "Persists and routes events according to partition or exchange rules."),
                ("Consumer group", "Coordinates parallel processing and ownership."),
                ("Retry/DLQ path", "Contains poison messages without blocking healthy traffic."),
            ),
            (
                "A producer writes an event using a deterministic routing or partition key.",
                "The broker persists and exposes the event to eligible consumers.",
                "A consumer processes the event inside an idempotency boundary.",
                "Offsets or acknowledgements advance only after durable side effects.",
                "Repeated failure moves the event to a bounded recovery workflow.",
            ),
            (
                "Define delivery semantics in terms of business side effects, not marketing labels.",
                "Use idempotency keys and transactional outbox/inbox patterns where needed.",
                "Separate immediate retries from delayed retries and manual recovery.",
                "Design partition keys to preserve required ordering without creating hotspots.",
            ),
            (
                "Poison messages cause infinite redelivery.",
                "A consumer commits progress before its side effect is durable.",
                "Rebalancing pauses processing or duplicates in-flight work.",
            ),
            ("consumer lag", "publish latency", "redelivery rate", "DLQ depth", "processing duration", "partition skew"),
            ("authenticate producers and consumers", "authorize topics/queues", "encrypt transport", "avoid sensitive data in headers"),
            ("Queues simplify work distribution; logs favor replay and multiple independent consumers.", "Exactly-once outcomes usually require idempotent application design and transactional boundaries."),
        ),
    ),
    (
        ("analytics", "window", "mapreduce", "anomaly", "alert", "dashboard", "search", "index", "query", "ranking"),
        TopicProfile(
            "analytics-search",
            "Transform event streams into queryable state, aggregates, alerts, and explanations while controlling freshness and computational cost.",
            (
                ("Ingestion/indexing pipeline", "Builds searchable structures or aggregates from incoming events."),
                ("State store", "Maintains windows, indexes, or materialized views."),
                ("Query service", "Plans and executes user or machine queries."),
                ("Alert evaluator", "Turns derived conditions into controlled notifications."),
            ),
            (
                "Events are assigned event time and normalized dimensions.",
                "Processing updates indexes, windows, or materialized aggregates.",
                "Queries read the smallest structure that can answer the request.",
                "Alert state suppresses duplicates and records lifecycle transitions.",
            ),
            (
                "Separate event time from processing time and define late-data handling.",
                "Choose index and aggregation structures from actual query patterns.",
                "Bound cardinality and retention for derived state.",
                "Make alerts stateful, deduplicated, and explainable.",
            ),
            (
                "Late events corrupt windowed results.",
                "High-cardinality dimensions exhaust memory.",
                "Indexing falls behind ingestion and returns stale results.",
            ),
            ("indexing lag", "query p95/p99 latency", "result freshness", "alert precision", "state-store size", "cache hit rate"),
            ("apply field-level authorization to query results", "redact sensitive dimensions", "audit privileged searches"),
            ("Precomputation speeds reads but increases write amplification.", "Exact analytics cost more than approximate or sampled results."),
        ),
    ),
    (
        ("failover", "circuit breaker", "backpressure", "chaos", "availability", "fault tolerance", "disaster recovery"),
        TopicProfile(
            "reliability",
            "Keep useful service available during overload and component failure while preventing local faults from becoming systemic outages.",
            (
                ("Health model", "Distinguishes process liveness from dependency readiness."),
                ("Failure isolation", "Bulkheads, timeouts, and circuit breakers contain blast radius."),
                ("Recovery controller", "Retries, fails over, or sheds load using bounded policies."),
                ("Chaos and recovery tests", "Verify assumptions before production incidents."),
            ),
            (
                "A request enters through an admission-control boundary.",
                "Timeout and concurrency budgets protect each dependency call.",
                "Failures update circuit and health state.",
                "Fallback, failover, or load shedding preserves critical functions.",
                "Recovery probes restore normal routing gradually.",
            ),
            (
                "Assign timeouts from end-to-end latency budgets.",
                "Use bounded retries with jitter and retry budgets.",
                "Separate critical from optional workloads.",
                "Test dependency slowness, not only complete failure.",
            ),
            (
                "Retry storms amplify an outage.",
                "A false-positive health check causes unnecessary failover.",
                "Backpressure is ignored and memory becomes the queue.",
            ),
            ("availability", "error-budget burn", "timeout rate", "circuit state changes", "queue depth", "failover duration"),
            ("protect recovery controls from unauthorized use", "retain incident evidence", "avoid exposing sensitive dependency details"),
            ("Aggressive failover improves recovery time but can create split-brain risk.", "Load shedding preserves core service by intentionally rejecting lower-priority work."),
        ),
    ),
    (
        ("rbac", "encryption", "redaction", "audit", "retention", "gdpr", "compliance", "security", "access control"),
        TopicProfile(
            "security-compliance",
            "Apply least privilege, data protection, traceability, and lifecycle policy without making the platform unusable for operations.",
            (
                ("Identity and policy layer", "Resolves principals, roles, attributes, and permitted actions."),
                ("Protection pipeline", "Encrypts, tokenizes, or redacts sensitive fields."),
                ("Audit ledger", "Records security-relevant decisions and access."),
                ("Lifecycle controller", "Applies retention, legal hold, export, and deletion policy."),
            ),
            (
                "The caller is authenticated and mapped to tenant and role context.",
                "Policy is evaluated against the requested resource and fields.",
                "Sensitive data is transformed before storage or disclosure.",
                "Every privileged action emits an immutable audit event.",
                "Lifecycle jobs enforce retention and approved deletion workflows.",
            ),
            (
                "Centralize policy semantics while keeping enforcement close to data access.",
                "Separate encryption keys from encrypted data and rotate them safely.",
                "Design deletion and retention against replicas, caches, indexes, and backups.",
                "Make audit records tamper-evident and searchable by authorized teams.",
            ),
            (
                "A broad role grants unintended cross-tenant access.",
                "Redaction happens after data has already entered logs or analytics.",
                "Deletion removes primary records but leaves derived copies.",
            ),
            ("authorization denials", "privileged access count", "key age", "redaction coverage", "retention backlog", "audit write failures"),
            ("least privilege", "separation of duties", "key-management controls", "immutable auditing", "privacy-by-default schemas"),
            ("Stronger controls add latency and operational process.", "Field-level protection preserves utility but requires metadata and key governance."),
        ),
    ),
    (
        ("profile", "batching", "cache", "bloom", "encoding", "optimization", "memory", "cpu", "performance"),
        TopicProfile(
            "performance",
            "Improve throughput, latency, and cost using measurements and workload-specific changes without weakening correctness.",
            (
                ("Workload model", "Defines traffic shape, payload size, concurrency, and SLOs."),
                ("Measurement layer", "Captures stage timing, resource use, and queueing."),
                ("Optimization mechanism", "Batching, caching, indexing, compression, or allocation change."),
                ("Regression guard", "Automated benchmark and threshold comparison."),
            ),
            (
                "Representative load enters the system with traceable request IDs.",
                "Stage-level measurements identify waiting, CPU, I/O, and contention.",
                "One controlled optimization is introduced.",
                "Correctness and failure behavior are revalidated before comparing metrics.",
            ),
            (
                "Establish a baseline and performance budget first.",
                "Optimize the dominant bottleneck rather than the most visible code.",
                "Measure tail latency and saturation, not only averages.",
                "Automate regression detection with stable datasets.",
            ),
            (
                "A cache returns stale or unauthorized data.",
                "Batching improves throughput but violates latency SLOs.",
                "Compression reduces I/O while saturating CPU.",
            ),
            ("throughput", "p50/p95/p99 latency", "CPU", "memory", "I/O wait", "queueing time", "cost per event"),
            ("include tenant and authorization boundaries in cache keys", "avoid sensitive data in benchmark artifacts", "protect profiling endpoints"),
            ("Caching trades freshness and invalidation complexity for speed.", "Batching trades individual latency for amortized efficiency."),
        ),
    ),
    (
        ("api", "graphql", "rate limit", "sdk", "cli", "webhook", "web ui", "dashboard", "real-time"),
        TopicProfile(
            "service-experience",
            "Expose platform capabilities through stable contracts, controlled resource usage, and observable client interactions.",
            (
                ("API contract", "Defines resources, commands, errors, pagination, and versioning."),
                ("Gateway or policy layer", "Applies authentication, quotas, validation, and routing."),
                ("Application service", "Coordinates domain logic and durable side effects."),
                ("Client surface", "SDK, CLI, webhook, or UI adapted to user workflows."),
            ),
            (
                "A client submits a versioned request with identity and correlation context.",
                "The edge validates quotas, shape, and authorization.",
                "The service executes the operation and records durable state.",
                "Responses or asynchronous callbacks expose progress and outcome.",
            ),
            (
                "Design idempotency and pagination before public release.",
                "Use explicit error models and retry guidance.",
                "Separate command APIs from high-volume streaming paths.",
                "Generate SDKs only after the contract and compatibility policy are stable.",
            ),
            (
                "Clients retry non-idempotent operations.",
                "Webhook consumers are slow or unavailable.",
                "Unbounded queries exhaust shared resources.",
            ),
            ("request rate", "error rate", "quota rejections", "response latency", "webhook delivery success", "active sessions"),
            ("strong authentication", "tenant-aware authorization", "input validation", "signed webhooks", "abuse prevention"),
            ("Flexible query APIs improve client productivity but complicate cost control.", "Push updates reduce polling but require connection lifecycle and replay design."),
        ),
    ),
    (
        ("tenant", "billing", "quota", "sso", "ldap", "enterprise"),
        TopicProfile(
            "multi-tenancy",
            "Share infrastructure safely while preserving tenant isolation, independent policy, predictable performance, and accountable usage.",
            (
                ("Tenant context", "Propagates tenant identity through every request and event."),
                ("Isolation controls", "Partition data, caches, queues, and resources."),
                ("Policy and configuration", "Applies tenant-specific limits and behavior."),
                ("Metering", "Records usage for capacity, chargeback, or billing."),
            ),
            (
                "Identity resolution establishes tenant context.",
                "Every storage and messaging key includes or derives tenant scope.",
                "Resource governors apply quotas and fairness.",
                "Usage events feed reporting and billing reconciliation.",
            ),
            (
                "Make tenant context mandatory and non-overridable in trusted middleware.",
                "Choose isolation level per risk: logical, schema, database, account, or cluster.",
                "Test noisy-neighbor scenarios and cross-tenant cache leakage.",
                "Reconcile metering events against durable source records.",
            ),
            (
                "A missing tenant predicate leaks data.",
                "One tenant monopolizes shared partitions.",
                "Offboarding leaves keys, backups, or derived data behind.",
            ),
            ("usage by tenant", "quota rejections", "cross-tenant authorization denials", "resource fairness", "billing reconciliation variance"),
            ("tenant-scoped encryption and authorization", "administrative separation", "audited support access", "secure offboarding"),
            ("Shared infrastructure lowers cost but increases isolation complexity.", "Physical isolation improves assurance but reduces elasticity and increases operations."),
        ),
    ),
    (
        ("monitor", "metric", "tracing", "testing", "benchmark", "debug", "diagnostic", "snapshot", "root cause"),
        TopicProfile(
            "observability-testing",
            "Make distributed behavior explainable and verifiable by correlating signals, testing invariants, and preserving evidence across failures.",
            (
                ("Telemetry instrumentation", "Produces metrics, logs, and traces with shared context."),
                ("Collection pipeline", "Buffers, samples, and transports telemetry."),
                ("Analysis layer", "Builds dashboards, alerts, traces, and diagnostic views."),
                ("Verification suite", "Exercises correctness, performance, recovery, and long-running stability."),
            ),
            (
                "A request or event receives correlation and trace context.",
                "Each component records stage timing and state transitions.",
                "Telemetry is aggregated without losing tenant and version dimensions.",
                "Alerts point to evidence and runbooks rather than isolated symptoms.",
            ),
            (
                "Define service-level indicators from user outcomes.",
                "Instrument boundaries and queues before adding verbose internal logs.",
                "Use deterministic tests for invariants and controlled chaos for recovery.",
                "Retain enough evidence for post-incident reconstruction.",
            ),
            (
                "High-cardinality labels overload telemetry storage.",
                "Sampling removes the only trace of rare failures.",
                "Tests validate happy paths but not retries and partial completion.",
            ),
            ("SLO attainment", "trace coverage", "telemetry drop rate", "mean time to detect", "mean time to recover", "test flake rate"),
            ("redact secrets and PII from telemetry", "restrict production debugging", "audit diagnostic access"),
            ("More telemetry improves diagnosis but raises cost and privacy risk.", "Sampling controls volume but can hide low-frequency failures."),
        ),
    ),
)


DEFAULT_PROFILE = TopicProfile(
    "distributed-component",
    "Add one bounded capability to the evolving platform while preserving explicit contracts, failure behavior, and operational visibility.",
    (
        ("Input boundary", "Validates and normalizes incoming work."),
        ("Core component", "Performs the lesson’s primary responsibility."),
        ("State boundary", "Stores durable state or progress where required."),
        ("Output boundary", "Publishes results through a stable contract."),
    ),
    (
        "Input arrives with identity, version, and correlation context.",
        "The component validates preconditions and applies the core operation.",
        "State changes are made durable before success is acknowledged.",
        "Results and operational signals are emitted for downstream use.",
    ),
    (
        "Define inputs, outputs, invariants, and failure semantics.",
        "Keep external dependencies behind interfaces.",
        "Add idempotency or deduplication when operations may repeat.",
        "Write tests for success, malformed input, dependency failure, and restart.",
    ),
    (
        "Partial completion leaves state inconsistent.",
        "Retries duplicate side effects.",
        "Dependency slowness consumes all worker capacity.",
    ),
    ("throughput", "latency", "error rate", "retry rate", "resource saturation"),
    ("authenticate callers", "validate input", "minimize sensitive data", "audit privileged changes"),
    ("A simpler design is easier to operate but may defer scalability.", "Extra abstraction improves replaceability but increases development cost."),
)


def infer_profile(title: str) -> TopicProfile:
    normalized = re.sub(r"[^a-z0-9]+", " ", title.lower())
    best_profile = DEFAULT_PROFILE
    best_score = 0
    for keywords, profile in PROFILES:
        score = sum(1 for keyword in keywords if keyword in normalized)
        if score > best_score:
            best_profile = profile
            best_score = score
    return best_profile


def infer_topic_tags(title: str) -> list[str]:
    profile = infer_profile(title)
    words = re.findall(r"[a-z0-9]+", title.lower())
    candidates = [profile.key]
    for phrase in (
        "distributed systems",
        "log processing",
        "fault tolerance",
        "access control",
        "data retention",
        "stream processing",
        "multi tenant",
        "real time",
    ):
        if all(part in words for part in phrase.split()):
            candidates.append(phrase.replace(" ", "-"))
    return list(dict.fromkeys(candidates))


def _bullets(values: Iterable[str]) -> str:
    return "\n".join(f"- {value}" for value in values)


def build_course_study_guide(
    *,
    lesson,
    previous_lesson,
    next_lesson,
    public_content: str,
    access_level: str,
) -> str:
    profile = infer_profile(lesson.title)
    previous_text = (
        f"Day {previous_lesson.day} — {previous_lesson.title}" if previous_lesson else "the course foundation"
    )
    next_text = (
        f"Day {next_lesson.day} — {next_lesson.title}" if next_lesson else "the completed platform"
    )
    public_signal = (
        "The public article or preview is included above and can be used as supporting material."
        if public_content
        else "Only the public curriculum objective is available, so this guide is derived from the stated topic and expected output."
    )

    component_rows = "\n".join(
        f"| {name} | {responsibility} |" for name, responsibility in profile.components
    )
    flow = "\n".join(f"{index}. {step}" for index, step in enumerate(profile.flow, start=1))
    implementation = "\n".join(
        f"{index}. {step}" for index, step in enumerate(profile.implementation, start=1)
    )

    return f"""## Original Stitched Study Guide

> This is original explanatory material generated from the public curriculum metadata and any publicly visible article text. It does not recreate or claim to reproduce subscriber-only course material.

### Lesson Position

- Current lesson: **Day {lesson.day} — {lesson.title}**
- Module: **{lesson.module}**
- Week: **{lesson.week}**
- Builds on: **{previous_text}**
- Prepares for: **{next_text}**
- Public access classification: **{access_level}**

{public_signal}

### Outcome to Produce

{lesson.expected_output or "Create a working, testable increment that demonstrates the lesson objective."}

### Why This Lesson Exists

{profile.role}

This lesson should not be implemented as an isolated demo. Treat it as the next production-shaped increment in one evolving LogStream platform. Preserve contracts from earlier days, introduce the smallest new responsibility, and leave observable seams for the next lesson.

### Conceptual Model

The system should make four things explicit:

1. **Contract:** What input is accepted, what output is promised, and how versions are handled.
2. **Durability boundary:** At which point the system may safely acknowledge success.
3. **Failure boundary:** Which failures are retried, rejected, quarantined, or surfaced.
4. **Operational evidence:** Which metrics, logs, traces, and state transitions prove correct behavior.

### Reference Components

| Component | Responsibility |
|---|---|
{component_rows}

### Reference Data Flow

{flow}

### Implementation Blueprint

{implementation}

### Failure Scenarios to Design Before Coding

{_bullets(profile.failures)}

For every failure, record the expected system response, whether the operation is safe to retry, and what evidence an operator receives.

### Observability Checklist

{_bullets(profile.metrics)}

Add correlation identifiers and stage timing so that queueing, dependency time, processing time, and durable-write time can be distinguished.

### Security and Governance

{_bullets(profile.security)}

Security checks should be part of normal request and event processing, not a separate afterthought.

### Important Trade-offs

{_bullets(profile.tradeoffs)}

Write down which side of each trade-off this lesson chooses and what future condition would justify changing it.

### Validation Plan

1. **Contract test:** Verify valid, invalid, boundary-size, and version-mismatch inputs.
2. **Restart test:** Interrupt the component during work and confirm recovery semantics.
3. **Dependency-failure test:** Make one downstream dependency slow, unavailable, and intermittently failing.
4. **Load test:** Increase throughput until the first resource saturates; identify the backpressure point.
5. **Data-integrity test:** Verify duplicates, reordering, and partial retries do not corrupt the intended outcome.
6. **Operational test:** Confirm dashboards and logs explain both successful and failed executions.

### Suggested Architecture Diagram

```mermaid
flowchart LR
    A[Previous lesson capability] --> B[Day {lesson.day}: {lesson.title}]
    B --> C[Durable state or handoff]
    C --> D[Next lesson capability]
    B --> E[Metrics / Logs / Traces]
    B --> F[Retry / Quarantine / Recovery]
```

### Questions to Answer in Your Own Words

1. What invariant must remain true even after process or network failure?
2. Where is the acknowledgement or commit boundary?
3. What makes a retry safe?
4. Which data must be ordered, and by what key?
5. Which metric would reveal overload before users notice?
6. How does this lesson change the architecture built on {previous_text}?
7. What interface must remain stable for {next_text}?
"""

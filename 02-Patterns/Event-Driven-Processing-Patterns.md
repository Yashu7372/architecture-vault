# Event-Driven Processing Patterns

## Goal

Capture practical event-driven patterns used in high-scale systems: batch processing, bucket/group processing, parallel user processing, and client-wise listeners.

These patterns are useful for feeds, notifications, operational dashboards, flight/ULD processing, baggage events, and multi-tenant systems.

---

## 1. Base Event Flow

```text
Producer Service
   |
   v
Event Broker / Kafka / Solace
   |
   v
Consumer Group
   |
   v
Processor
   |
   +--> State Store / Couchbase / Redis
   +--> Audit Store / Oracle / PostgreSQL
   +--> Notification / SSE / WebSocket
```

The core idea is simple:

> Events should be consumed once logically, processed idempotently, grouped correctly, and pushed only to the users/clients who need them.

---

## 2. Batch Processing Pattern

### Problem

Processing each event individually can overload DB, cache, and downstream APIs.

Example:

```text
10,000 bag events arrive in 1 minute.
If each event performs one DB write, DB load becomes high.
```

### Pattern

Collect events for a short time window or fixed size, then process together.

```text
Events -> Consumer -> In-memory batch -> Bulk DB/cache write -> Commit offset/ack
```

### Common Batch Rules

```text
batchSize = 500
flushInterval = 2 seconds
maxRetry = 3
```

Flush when either:

- batch size is reached
- flush interval is reached
- partition/shard is rebalanced
- application is shutting down

### Example

```java
class BatchProcessor {
    private final List<Event> buffer = new ArrayList<>();

    public void onEvent(Event event) {
        buffer.add(event);

        if (buffer.size() >= 500) {
            flush();
        }
    }

    public void flush() {
        repository.bulkUpsert(buffer);
        buffer.clear();
    }
}
```

### When to Use

- Bulk inserts
- Counter updates
- Audit writes
- Timeline fanout
- Notification aggregation
- Report precomputation

### DNBMS Mapping

Instead of writing every bag event separately to Oracle, collect by flight/ULD and do batch MERGE or Couchbase bulk mutation.

---

## 3. Bucket / Group Processing Pattern

### Problem

Events belong to natural groups. Processing them randomly creates race conditions and unnecessary recalculation.

Examples:

```text
Twitter: userId / authorId / timelineId
DNBMS: flightId / uldId / station / tenant
WhatsApp CRM: tenantId / conversationId
```

### Pattern

Route events into buckets using a stable key.

```text
eventKey = flightId
bucket = hash(eventKey) % bucketCount
```

All events for the same key go to the same bucket, preserving order for that key.

```text
Event Broker
   |
   +--> Bucket 0 -> Worker 0
   +--> Bucket 1 -> Worker 1
   +--> Bucket 2 -> Worker 2
   +--> Bucket 3 -> Worker 3
```

### Example

```java
int bucketId = Math.abs(event.flightId().hashCode()) % 16;
bucketQueues.get(bucketId).offer(event);
```

### Why It Helps

- Keeps same flight/user/conversation ordered.
- Allows different buckets to run in parallel.
- Reduces locking.
- Makes replay easier.
- Limits blast radius if one bucket is slow.

### DNBMS Mapping

For operational events, bucket by:

```text
flightKey = station + flightNumber + flightDate
```

Then all bag/ULD events for that flight are handled sequentially inside the bucket, while other flights run in parallel.

---

## 4. Parallel User Processing Pattern

### Problem

A single event may affect many users.

Example:

```text
One post affects 10,000 follower timelines.
One flight event affects many dashboard users subscribed to that flight.
```

Processing users one by one is slow.

### Pattern

Split affected users into chunks and process chunks in parallel.

```text
PostCreated / FlightChanged Event
       |
       v
Find affected users
       |
       v
Split into chunks of 500
       |
       +--> Worker 1 processes users 1-500
       +--> Worker 2 processes users 501-1000
       +--> Worker 3 processes users 1001-1500
```

### Example

```java
List<List<UserId>> chunks = Lists.partition(affectedUsers, 500);

chunks.parallelStream().forEach(chunk -> {
    timelineStore.bulkAppend(chunk, event);
});
```

### Important Rules

- Keep idempotency key per user + event.
- Limit max parallelism.
- Use bulk writes.
- Track partial failures.
- Retry failed chunks, not the full event if possible.

### Idempotency Key

```text
idempotencyKey = eventId + ':' + userId
```

### DNBMS Mapping

If a flight count changes, do not push to all connected users blindly. First resolve subscriptions:

```text
flightId -> subscribed users/groups -> chunk -> parallel notify
```

---

## 5. Client-Wise Listener Pattern

### Problem

Different clients may need the same event in different formats or with different filters.

Examples:

```text
Mobile app needs compact payload.
Admin dashboard needs full payload.
Partner API needs only approved fields.
Tenant A and Tenant B need strict data isolation.
```

### Pattern

Keep one core event, then create client-specific listeners/adapters.

```text
Core Event Topic
     |
     +--> Web Dashboard Listener
     +--> Mobile Listener
     +--> Partner API Listener
     +--> Tenant-Specific Listener
     +--> Audit Listener
```

Each listener handles:

- filtering
- transformation
- authorization
- rate limiting
- delivery format
- retry policy

### Example

```text
bag.event.updated
   |
   +--> dashboard-projection-listener
   +--> mobile-notification-listener
   +--> audit-persistence-listener
   +--> partner-integration-listener
```

### Why It Helps

- Core domain event remains clean.
- Client logic does not pollute producer service.
- New client can be added without changing core producer.
- Failures are isolated per listener.

### DNBMS Mapping

A single `BagStatusChangedEvent` can feed:

```text
- AFS dashboard SSE projection
- Notification service
- Oracle audit writer
- Alert rule service
- Mobile app listener
```

---

## 6. Consumer Group Pattern

Multiple instances of the same service can share work.

```text
Topic: post.created
Consumer Group: timeline-fanout-service

Instance 1 -> partition 0,1
Instance 2 -> partition 2,3
Instance 3 -> partition 4,5
```

Rules:

- Same consumer group = load sharing.
- Different consumer groups = each group receives its own copy.
- Use event key to preserve ordering for important entities.

For DNBMS:

```text
Topic: bag.status.changed
Consumer Group 1: afs-projection-service
Consumer Group 2: oracle-audit-service
Consumer Group 3: alert-rule-service
Consumer Group 4: notification-service
```

---

## 7. Backpressure Pattern

### Problem

Consumers may receive events faster than they can process.

### Handling Options

- Pause consumption temporarily.
- Increase batch size.
- Scale consumers.
- Drop non-critical UI refresh events.
- Merge multiple events for the same key.
- Send failed events to DLQ.

### Merge Example

If 100 updates arrive for the same flight in 2 seconds, UI may not need 100 pushes.

```text
flightId=EK001 -> merge -> send latest count only
```

This is very useful for dashboards.

---

## 8. Recommended Pattern for Operational Dashboards

For systems like DNBMS, use this approach:

```text
1. Event arrives from Solace/Kafka.
2. Partition/bucket by flightKey or uldKey.
3. Process events sequentially inside the same bucket.
4. Update Couchbase projection/counter.
5. Write Oracle audit in batch.
6. Resolve subscribed users/groups.
7. Send SSE notification in chunks.
8. Use idempotency key to avoid duplicates.
```

Architecture:

```text
Solace Topic
   |
   v
Common SDK Consumer
   |
   v
Bucket Router by flightKey
   |
   +--> Bucket Worker 1
   +--> Bucket Worker 2
   +--> Bucket Worker 3
   |
   v
Projection Store / Couchbase
   |
   +--> Oracle Batch Audit
   +--> Notification Fanout
   +--> SSE Gateway
```

---

## 9. Key Design Decisions

| Decision | Recommended Choice |
|---|---|
| Ordering key | flightId/userId/conversationId depending on domain |
| Parallelism | Across buckets, not inside same entity key |
| DB writes | Batch/bulk writes |
| UI push | Merge and send latest state |
| Retry | Retry per chunk/bucket |
| Idempotency | eventId + entityId or eventId + userId |
| Listener design | Separate client-wise listeners |

---

## 10. Interview Explanation

A strong answer:

> I would not process all events one by one with direct DB calls. I would key events by domain entity, route them into buckets, process each bucket sequentially for ordering, run buckets in parallel for throughput, batch DB/cache writes, and have separate listeners for dashboard, mobile, audit, and alerting. For user fanout, I would resolve subscribers and process users in chunks with idempotency and retry.

---

## 11. Key Learning

Event-driven architecture is not only about publishing events. The real design is about:

- partitioning
- ordering
- batching
- idempotency
- backpressure
- client-specific delivery
- replay and recovery

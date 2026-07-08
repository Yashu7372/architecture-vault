# Hot-Row Contention & Counter Sharding

## Problem Evolution

**v1 — naive counter column**
```sql
UPDATE title_stats SET view_count = view_count + 1 WHERE title_id = ?;
```
Fine at low volume. Each update takes a row lock, does its increment, commits.

**v2 — a title goes viral**
Thousands of concurrent sessions hit the *same row*. Every `UPDATE` now
queues behind the previous one's row lock. Latency on this one endpoint
climbs from 2ms to 2s. Because the lock is row-level, it doesn't matter how
good your indexes are — you're serialized by definition. In Oracle/Postgres
you'll see sessions piling up on a `TX`/row-lock wait; in MySQL/InnoDB,
`InnoDB row lock wait`.

**v3 — "just batch the updates in the app"**
Someone adds an in-memory counter in the app layer that flushes every N
seconds. This helps until you have multiple app instances (each with its
own in-memory counter racing to flush) or the instance dies and loses
un-flushed counts. Now you have both a contention problem *and* a
durability/accuracy problem.

**v4 — the actual fix: stop mutating one row**

---

## Production Architecture

Replace "one row, mutated in place" with **append-only deltas, aggregated
on read**, or **counter sharding** — spread the hot value across N physical
rows so writers don't collide.

### Option A — Sharded counter rows

```sql
CREATE TABLE title_view_counter (
    title_id   BIGINT NOT NULL,
    shard_id   SMALLINT NOT NULL,   -- 0..15, chosen randomly per writer
    view_count BIGINT NOT NULL DEFAULT 0,
    PRIMARY KEY (title_id, shard_id)
);
```

Each writer picks `shard_id = random(0, 15)` and updates only that shard:

```sql
UPDATE title_view_counter
SET view_count = view_count + 1
WHERE title_id = ? AND shard_id = ?;
```

Reads roll the shards up:

```sql
SELECT title_id, SUM(view_count) AS total_views
FROM title_view_counter
WHERE title_id = ?
GROUP BY title_id;
```

16 shards turns one hot row into 16 mildly-warm rows — contention drops
~16x. Shard count is a tuning knob: more shards = less write contention but
more read-side aggregation cost and more storage.

### Option B — Append-only event log + periodic rollup

```sql
CREATE TABLE view_event (
    title_id BIGINT NOT NULL,
    occurred_at TIMESTAMP NOT NULL DEFAULT now()
    -- no update, ever — just inserts
);
```

Inserts to a table never contend with each other the way updates to the
same row do (different physical rows, no shared lock). A background job
rolls these up into `title_stats.view_count` every minute via conditional
aggregation:

```sql
INSERT INTO title_stats (title_id, view_count)
SELECT title_id, COUNT(*)
FROM view_event
WHERE occurred_at >= :window_start AND occurred_at < :window_end
GROUP BY title_id
ON CONFLICT (title_id) DO UPDATE
SET view_count = title_stats.view_count + EXCLUDED.view_count;
```

Use A when you need a near-real-time counter and can tolerate slightly more
complex reads. Use B when you need the raw events anyway (for later
analytics) and can tolerate near-real-time rather than instant counts.

---

## Partitioning & Sharding

- `shard_id` in Option A is a **logical** shard — it doesn't require the
  table itself to be partitioned, but on a very large table you can range/
  hash-partition `title_view_counter` by `title_id` so hot titles' shards
  are physically co-located and cold titles don't bloat the same pages.
- Option B's `view_event` table is a natural candidate for **date-range
  partitioning** (`occurred_at`) so old partitions can be dropped/archived
  cheaply once rolled up.

---

## Batch vs Streaming Processing

- Option A is inherently "streaming" — every write updates state
  immediately, just spread across shards.
- Option B is batch-oriented — writes are cheap and immediate, but the
  *visible* counter lags by one rollup interval. If the UI needs
  "approximately real-time," add `SELECT COUNT(*) FROM view_event WHERE
  title_id = ? AND occurred_at >= :last_rollup_time` and add it to the
  last rolled-up value for a live estimate without re-scanning history.

---

## Hot-Key / Celebrity Mitigation

This *is* the celebrity/hot-partition problem in DB form: a small number of
keys (viral titles, trending flights, top accounts) receive
disproportionate write volume. The generalizable rule: **detect skew, and
only pay the sharding/append-log cost for the keys that need it** — don't
shard every counter in the system by default, since it adds read-side
aggregation overhead everywhere. A common production pattern is to start
every title on Option B (cheap, general) and only promote clearly-viral
titles to a dedicated high-shard-count counter.

---

## Backpressure

If write volume to `view_event` spikes beyond what the DB can absorb, put a
bounded queue (Kafka/SQS) in front of the insert path so the DB sees a
smooth, batched insert rate (e.g. `INSERT ... VALUES (...), (...), (...)`
in batches of 500) instead of unbounded direct writes from every client.

---

## Idempotency

Both options are naturally idempotent-*ish*: Option A's `+1` is not
idempotent (a retried request double-counts) — pair it with a
client-generated `request_id` deduped via a short-TTL cache or a unique
constraint on `(title_id, session_id, event_minute)` if exact-once counting
matters. Option B gets this almost for free: give `view_event` a unique
constraint on the natural key of the event and use `INSERT ... ON CONFLICT
DO NOTHING`.

---

## Observability & Metrics

- Track **lock wait time** / **row contention** metrics (`pg_stat_activity`
  wait events, Oracle `v$session` `wait_class = 'Concurrency'`) per table —
  this is the leading indicator that a row is about to become hot, before
  users notice latency.
- Track shard skew: if one `shard_id` gets picked disproportionately, your
  random shard selection has a bug (e.g. weak RNG, or a client pinning a
  seed).

---

## Failure Scenarios

- **Rollup job falls behind** (Option B): reads show stale counts. Alert on
  rollup lag (`now() - MAX(processed_through)`), and make the live-estimate
  query (above) the fallback rather than blocking on the rollup.
- **Shard count is too low for the actual spike** (Option A): contention
  reappears at a higher volume threshold. Shard count should be
  configurable, not hardcoded, so it can be bumped without a migration
  (e.g. via a `shard_count` config row and modulo-hashing on write).

---

## Java / Spring Boot Implementation Ideas

```java
@Repository
public class TitleViewCounterRepository {

    private final JdbcTemplate jdbc;
    private static final int SHARD_COUNT = 16;

    public void recordView(long titleId) {
        int shard = ThreadLocalRandom.current().nextInt(SHARD_COUNT);
        jdbc.update("""
            INSERT INTO title_view_counter (title_id, shard_id, view_count)
            VALUES (?, ?, 1)
            ON CONFLICT (title_id, shard_id)
            DO UPDATE SET view_count = title_view_counter.view_count + 1
            """, titleId, shard);
    }

    public long getTotalViews(long titleId) {
        Long total = jdbc.queryForObject("""
            SELECT SUM(view_count) FROM title_view_counter WHERE title_id = ?
            """, Long.class, titleId);
        return total == null ? 0L : total;
    }
}
```

For the append-log rollup, a `@Scheduled` job (or better, a dedicated
Spring Batch step) does the `INSERT ... SELECT ... GROUP BY` on a fixed
interval, with the window boundaries stored in a `rollup_checkpoint` table
so restarts don't reprocess or skip a window.

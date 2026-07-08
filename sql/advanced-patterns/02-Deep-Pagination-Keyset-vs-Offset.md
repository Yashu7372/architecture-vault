# Deep Pagination: Keyset vs Offset

## Problem Evolution

**v1 — `LIMIT`/`OFFSET`, works fine in dev**
```sql
SELECT * FROM watch_history
WHERE account_id = ?
ORDER BY watched_at DESC
LIMIT 20 OFFSET 0;
```
Page 1 is instant. Nobody notices a problem in a 10k-row dev dataset.

**v2 — production scale, users page deep**
Page 5000 (`OFFSET 100000`) forces the engine to walk the index (or scan)
100,020 rows and *throw away* the first 100,000 just to return the last 20.
Cost grows linearly with page depth — page 1 and page 5000 are not the same
query cost-wise, even though they look identical in code.

**v3 — "let's just add an index"**
An index on `(account_id, watched_at)` speeds up *finding* the rows, but
does nothing for the fundamental problem: the engine still has to walk and
discard `OFFSET` rows before it can start returning results. Index helps the
scan, not the discard.

**v4 — the actual fix: seek from a known position instead of counting from
the start**

---

## Production Architecture

### Keyset (seek) pagination

Instead of asking "give me rows 100,000–100,020," ask "give me the 20 rows
that come after the last one I saw":

```sql
SELECT id, account_id, title_id, watched_at
FROM watch_history
WHERE account_id = ?
  AND (watched_at, id) < (:last_watched_at, :last_id)   -- tuple comparison
ORDER BY watched_at DESC, id DESC
LIMIT 20;
```

- `id` is included as a tiebreaker because `watched_at` alone isn't unique
  (two events in the same millisecond would otherwise be skipped or
  duplicated across pages).
- Backed by a composite index `(account_id, watched_at DESC, id DESC)` —
  the engine seeks directly to the right spot and reads 20 rows forward.
  Cost is **constant** regardless of page depth.
- The client carries the cursor forward: `(last_watched_at, last_id)` from
  the last row of the previous page, typically opaque-encoded
  (base64 of those two values) so the API doesn't leak internal column
  names.

### Trade-off you're accepting

Keyset pagination can't jump to an arbitrary page number ("go to page 42")
— it only supports next/previous relative to a cursor. For UIs that need
numbered page jumps (admin dashboards, not infinite-scroll feeds), keep
`OFFSET` but cap how deep it's allowed to go (e.g. disallow `OFFSET >
10000`, or only allow deep jumps via a different, cheaper index like a
pre-computed row-number bucket).

---

## Partitioning & Sharding

If `watch_history` is sharded (e.g. by `account_id` hash, common in
multi-tenant systems), keyset pagination stays cheap because each query
already targets one shard via the equality predicate. Naive `OFFSET`
pagination across a sharded table is *worse* than on a single node — you'd
need to fan out to every shard, over-fetch `OFFSET + LIMIT` rows from each,
merge-sort in the application layer, then discard — turning one query into
N queries plus app-side merge work.

---

## Consumer Parallelism

For bulk export/ETL jobs reading the whole table (not a single user's
page), keyset pagination is what makes parallel workers possible: split the
primary key range into N buckets up front (`SELECT MIN(id), MAX(id) ...`
or pre-known ID boundaries) and give each worker a disjoint keyset range to
walk independently — no worker ever discards rows another worker already
owns, unlike trying to split `OFFSET` ranges across workers (which still
pays the discard cost per worker).

---

## Ordering Guarantees

Keyset pagination requires a **total order** — the `ORDER BY` columns must
uniquely determine row position (hence the `id` tiebreaker). Without a
tiebreaker, concurrent inserts at the same `watched_at` can cause a row to
be skipped or shown twice across pages. `OFFSET` pagination has this same
bug even more often — if rows are inserted/deleted between page fetches,
the "row 100,000" boundary shifts, silently skipping or duplicating rows
you already can't get back with `OFFSET` alone.

---

## Backpressure

For bulk streaming reads (an export job pulling millions of rows), don't
`SELECT *` the whole result set into memory — combine keyset pagination
with a bounded fetch size (`LIMIT 500` per round trip) so the consumer
naturally throttles itself to processing speed instead of the driver
buffering unbounded rows client-side.

---

## Observability & Metrics

- Track `rows_examined` vs `rows_returned` per paginated endpoint. A ratio
  that grows with page number is the signature of an `OFFSET` problem
  hiding in production traffic.
- Log/alert on `OFFSET` values above a threshold (e.g. `> 5000`) hitting
  the endpoint — that's a strong signal either a user is scrolling
  unreasonably deep or (more often) a bot/scraper is walking the whole
  dataset page by page.

---

## Failure Scenarios

- **Cursor tampering**: since the cursor carries real column values, a
  client could forge one to skip access-control filtering if the query
  isn't also re-applying `WHERE account_id = ?` server-side. Always encode
  the cursor as opaque and always re-apply the tenant/owner filter
  independently of what's in the cursor.
- **Schema change breaks cursor compatibility**: if the `ORDER BY` columns
  change, previously-issued cursors become meaningless. Version the cursor
  format so old clients fail cleanly (re-fetch page 1) instead of returning
  wrong data.

---

## Enterprise Mapping

Same shape applies anywhere a user or job pages through a large,
append-heavy table ordered by time or ID: audit logs, notification feeds,
transaction history, event streams for a downstream consumer catching up.
Anywhere "infinite scroll" or "resume from where I left off" shows up, this
is the pattern — not `OFFSET`.

---

## Java / Spring Boot Implementation Ideas

```java
public record WatchHistoryPage(List<WatchEvent> items, String nextCursor) {}

@Repository
public class WatchHistoryRepository {

    private final JdbcTemplate jdbc;

    public WatchHistoryPage getPage(long accountId, Cursor cursor, int pageSize) {
        String sql = """
            SELECT id, title_id, watched_at
            FROM watch_history
            WHERE account_id = ?
              AND (watched_at, id) < (?, ?)
            ORDER BY watched_at DESC, id DESC
            LIMIT ?
            """;
        List<WatchEvent> rows = jdbc.query(sql, rowMapper,
            accountId, cursor.watchedAt(), cursor.id(), pageSize);

        String next = rows.isEmpty() ? null
            : Cursor.encode(rows.get(rows.size() - 1));
        return new WatchHistoryPage(rows, next);
    }
}
```

`Cursor.encode`/`decode` base64-encode `(watched_at, id)` as an opaque
token; the controller never exposes raw column values in the API contract,
so the storage layer can evolve independently of the pagination contract.

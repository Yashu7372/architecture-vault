# SQL Optimization Techniques

## Source

- Modern SQL by Markus Winand
- PostgreSQL Exercises
- Use The Index, Luke

---

## Problem

The same result can be produced by a brute-force, procedural style (loop +
many small queries) or by a single set-based SQL statement. The procedural
style feels natural coming from Java, but it multiplies round trips, defeats
the query planner, and doesn't scale past a handful of items.

---

## Technique 1 — Conditional Aggregation Instead of N Queries

```sql
SUM(CASE WHEN condition THEN 1 ELSE 0 END)
```

Turns N separate `COUNT(*) WHERE flag = X` queries into N columns of a
single `GROUP BY` query. This is the single most useful pattern for
reporting/dashboard-style queries. See the full worked example in
[04](./04-conditional-aggregation-case-study.md).

## Technique 2 — Batch Filtering with Tuple `IN`

Instead of looping and issuing one query per key:

```sql
WHERE (flight_no, flight_date, origin) IN (
    ('EK001', DATE '2026-07-07', 'DXB'),
    ('EK002', DATE '2026-07-07', 'DXB')
)
```

Pass the whole batch (from the Java layer as a `List` bound in) in one round
trip. Works well up to a few hundred/thousand tuples; beyond that, prefer
joining against a temp table / table-valued parameter.

## Technique 3 — Join Against a Values List / Temp Table for Large Batches

For very large batches (thousands of keys), a giant `IN` list becomes its
own performance problem (parsing cost, plan size). Instead:

```sql
WITH keys (flight_no, flight_date, origin) AS (
    VALUES ('EK001', DATE '2026-07-07', 'DXB'),
           ('EK002', DATE '2026-07-07', 'DXB')
)
SELECT b.flight_no, b.flight_date, b.origin,
       COUNT(*) AS total_bags
FROM bag_detail b
JOIN keys k
  ON b.flight_no = k.flight_no
 AND b.flight_date = k.flight_date
 AND b.origin = k.origin
GROUP BY b.flight_no, b.flight_date, b.origin;
```

This lets the optimizer treat it like a normal join and pick a hash/merge
join if that's cheaper than N index lookups.

## Technique 4 — Window Functions Instead of Self-Joins/Subqueries

Running totals, rank-per-group, "latest row per group" — all avoid
correlated subqueries:

```sql
SELECT flight_no, bag_id, scan_time,
       ROW_NUMBER() OVER (PARTITION BY flight_no ORDER BY scan_time DESC) AS rn
FROM bag_scan_event;
```

Then filter `WHERE rn = 1` in an outer query (or `QUALIFY` in engines that
support it) to get "latest scan per flight" without a self-join.

## Technique 5 — CTEs for Readability, Not Automatically for Performance

`WITH` clauses make multi-step logic readable. In Postgres (≥12) and Oracle,
CTEs are typically inlined/optimized like subqueries; don't assume a CTE is
materialized (an optimization fence) unless the engine/version documents
that behavior — check before relying on it for performance.

## Technique 6 — Keyset (Seek) Pagination Instead of `OFFSET`

```sql
-- Slow at high offsets: DB must scan+discard N rows
SELECT * FROM bag_detail ORDER BY id LIMIT 20 OFFSET 100000;

-- Fast at any depth: seeks directly using the index
SELECT * FROM bag_detail WHERE id > :last_seen_id ORDER BY id LIMIT 20;
```

## Technique 7 — Avoid Wrapping Indexed Columns in Functions

```sql
-- Can't use a plain index on flight_date
WHERE TRUNC(flight_date) = DATE '2026-07-07'

-- Sargable — can use a range scan on the index
WHERE flight_date >= DATE '2026-07-07' AND flight_date < DATE '2026-07-08'
```

## Technique 8 — Select Only What You Need

`SELECT *` prevents index-only scans and pulls unnecessary I/O, especially
across a network boundary to a Java app that discards most columns anyway.

---

## Interview Questions

- Why is `SUM(CASE WHEN ...)` generally cheaper than N separate `COUNT`
  queries?
- When does a big `IN (...)` list become a problem, and what's the
  alternative?
- Why is keyset pagination better than `OFFSET` for deep pages?
- What does "sargable" mean and why does wrapping a column in a function
  break it?

---

## My Thoughts

- Default habit going forward: if I'm about to write a loop around a DB
  call in Java, stop and ask "can this be one query with a batch key list
  and conditional aggregation?" first.
- Push filtering/aggregation into SQL; don't pull rows into Java to filter
  or count them there.

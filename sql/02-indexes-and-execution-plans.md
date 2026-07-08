# Indexes & Execution Plans

## Source

- Use The Index, Luke
- Ask TOM / Oracle Docs

---

## Problem

An index doesn't automatically make a query fast — the wrong index (or the
right index used the wrong way) can be as slow as a full table scan. You
need to know what an index physically is, when the optimizer will actually
use it, and how to read an execution plan to confirm it's doing what you
think.

---

## Index Basics

- Most indexes (B-tree) are **sorted structures** on the indexed column(s),
  pointing back to the table row (via rowid/ctid or, in a clustered index,
  containing the row itself).
- An index is only useful if the query can use its **leading/leftmost**
  columns for equality or range filtering — like a phone book sorted by
  (last name, first name): you can jump to "Smith", but you can't jump to
  "people whose first name is John" without scanning every last name.

## Composite (Multi-Column) Index Design

Order columns as:

1. **Equality predicate columns first** (`flight_no = ?`, `flight_date = ?`)
2. **Range predicate columns next** (`created_at > ?`)
3. Columns only needed for **sorting or covering** (included so the index
   alone can satisfy the query — index-only scan) last

Example for the baggage case study:

```sql
CREATE INDEX idx_bag_detail_flight
    ON bag_detail (flight_no, flight_date, origin);
```

This lets a query filtering on all three columns (or a leading subset, e.g.
just `flight_no`) go straight to the matching rows instead of scanning the
whole table.

## Index-Only / Covering Scans

If every column the query needs (filter + select) is present in the index,
the engine can answer the query from the index alone, without a lookup back
to the table (a "table access by rowid" step). Adding non-key columns via
`INCLUDE` (Postgres/SQL Server) or as trailing index columns is a common way
to enable this for hot reporting queries.

## Reading an Execution Plan (`EXPLAIN` / `EXPLAIN ANALYZE`)

Look for:

- **Scan type**: `Seq Scan` / `TABLE ACCESS FULL` (bad for large selective
  queries) vs `Index Scan` / `Index Range Scan` vs `Index Only Scan`.
- **Join algorithm**: Nested Loop (good for small driving sets), Hash Join
  (good for large unsorted sets), Merge Join (good when both sides are
  already sorted on the join key).
- **Estimated vs actual rows** (`EXPLAIN ANALYZE`): a big gap means stale
  statistics or a bad cardinality estimate — a common root cause of bad plan
  choices.
- **Filter vs Index Condition**: a predicate applied as a post-scan
  `Filter` (after fetching rows) is doing more work than one applied as an
  `Index Cond` (used to narrow the index range itself).

```sql
EXPLAIN ANALYZE
SELECT flight_no, flight_date, origin, COUNT(*)
FROM bag_detail
WHERE flight_no = 'EK001' AND flight_date = DATE '2026-07-07'
GROUP BY flight_no, flight_date, origin;
```

---

## Interview Questions

- Why does column order matter in a composite index?
- What's the difference between an index range scan and an index-only scan?
- When would the optimizer *ignore* an index even though one exists on the
  filtered column? (low selectivity, small table, stale stats, function
  wrapping the column e.g. `UPPER(col) = ?` without a matching functional
  index)
- Why can adding an index make writes slower?

---

## My Thoughts

- Before adding an index, check selectivity: an index on a boolean flag
  (`loaded_flag = 'Y'/'N'`) alone is rarely useful since it doesn't narrow
  the row set much — pair it with the flight identifier columns instead.
- Always validate with `EXPLAIN` after adding an index — don't assume it's
  being used.

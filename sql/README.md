# SQL Internals & Optimization

## Source

- Use The Index, Luke
- PostgreSQL Exercises
- Ask TOM / Oracle Docs
- Modern SQL by Markus Winand

---

## Problem

As a Java developer writing reporting/batch queries, the default instinct is to
loop over a list (e.g. 50 flights) and fire one query per item. That doesn't
scale, doesn't use indexes well, and hides the real cost from the DB. The goal
of this folder is to understand *why* that's slow (how SQL actually gets
parsed and executed) and *how* to replace it with set-based SQL (joins,
`GROUP BY`, conditional aggregation, window functions, CTEs).

---

## Contents

1. [SQL Parsing & Execution Flow](./01-sql-parsing-and-execution.md)
2. [Indexes & Execution Plans](./02-indexes-and-execution-plans.md)
3. [Optimization Techniques](./03-optimization-techniques.md)
4. [Real Scenario: Bag Counts for 50 Flights](./04-conditional-aggregation-case-study.md)

---

## Must-Learn Concepts

- Joins (inner, outer, semi/anti via `EXISTS`/`IN`)
- `GROUP BY` and conditional aggregation (`SUM(CASE WHEN ...)`)
- Indexes, composite indexes, covering/index-only scans
- Reading an execution plan
- CTEs (`WITH`)
- Window functions (`ROW_NUMBER`, `RANK`, `SUM() OVER`)
- Pagination (offset vs keyset/seek)

---

## Key Pattern to Internalize

```sql
SUM(CASE WHEN condition THEN 1 ELSE 0 END)
```

This is how you get many counts out of **one** query instead of firing a
separate query per condition or per entity. See
[04](./04-conditional-aggregation-case-study.md) for the full worked example.

---

## My Thoughts

- Any time I catch myself looping over a list in Java to build N queries,
  stop and ask: can this become one query with `WHERE (col1, col2, col3) IN (...)`
  or a join against a temp table / values list, followed by `GROUP BY` with
  conditional aggregation?
- Pair every new query with `EXPLAIN` (or `EXPLAIN ANALYZE`) before shipping
  it — know which index it's using and why.
- Composite indexes should match the columns used in `WHERE`/`JOIN` first,
  in the order of equality predicates, then range predicates, then columns
  needed only for sorting/covering.

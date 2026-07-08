# Fan-Out Joins & Aggregation Fences

## Problem Evolution

**v1 — "just join everything and group at the end"**

A flight has many bags, and each bag has many scan events (loaded, offloaded,
rush-tagged, etc. — each recorded as its own row). Someone wants "bag count
and scan count per flight" in one query:

```sql
SELECT f.flight_no,
       COUNT(DISTINCT b.bag_id)  AS bag_count,
       COUNT(s.scan_id)          AS scan_count
FROM flight f
JOIN bag_detail b ON b.flight_no = f.flight_no
JOIN bag_scan_event s ON s.bag_id = b.bag_id
GROUP BY f.flight_no;
```

**v2 — the numbers are wrong, and nobody can figure out why**

If a bag has 4 scan events, the join produces 4 rows for that bag *before*
aggregation. `COUNT(DISTINCT b.bag_id)` happens to survive this because of
the `DISTINCT`, but any `SUM`/`COUNT` over a *bag-level* column (e.g.
`SUM(b.weight_kg)`) is now silently multiplied by however many scan events
each bag has. This is the classic **fan-out** bug: joining a "one" side to
a "many" side inflates every row from the "one" side proportionally to the
row count on the "many" side, and it inflates differently per bag (a bag
with 6 scans is over-counted more than a bag with 2).

**v3 — "let's add more DISTINCT everywhere"**

`SUM(DISTINCT ...)` doesn't mean what people think it means — it removes
duplicate *values*, not duplicate *rows tied to an entity*, so two
different bags that happen to weigh the same get silently collapsed into
one. This makes it worse, not better, and the bug becomes even harder to
spot because it's now wrong in a different, subtler way.

**v4 — the actual fix: aggregate each side separately before joining**

---

## Production Architecture

Pre-aggregate each "many" relationship in its own scope, so no join ever
multiplies rows across two different one-to-many relationships at once:

```sql
WITH bag_agg AS (
    SELECT flight_no, COUNT(*) AS bag_count, SUM(weight_kg) AS total_weight
    FROM bag_detail
    GROUP BY flight_no
),
scan_agg AS (
    SELECT b.flight_no, COUNT(*) AS scan_count
    FROM bag_scan_event s
    JOIN bag_detail b ON b.bag_id = s.bag_id
    GROUP BY b.flight_no
)
SELECT f.flight_no,
       COALESCE(bag_agg.bag_count, 0)     AS bag_count,
       COALESCE(bag_agg.total_weight, 0)  AS total_weight,
       COALESCE(scan_agg.scan_count, 0)   AS scan_count
FROM flight f
LEFT JOIN bag_agg  ON bag_agg.flight_no = f.flight_no
LEFT JOIN scan_agg ON scan_agg.flight_no = f.flight_no;
```

Each CTE aggregates exactly one one-to-many relationship down to one row
per flight *before* the final join — so the final join is one-to-one (or
one-to-zero-or-one with the `LEFT JOIN`s), which can never multiply rows.
This is the general rule: **an aggregation fence goes between any join and
any other join that shares the same grouping grain but a different fan-out
factor.**

### Alternative: correlated subqueries per metric

```sql
SELECT f.flight_no,
       (SELECT COUNT(*) FROM bag_detail b WHERE b.flight_no = f.flight_no) AS bag_count,
       (SELECT COUNT(*) FROM bag_scan_event s
          JOIN bag_detail b ON b.bag_id = s.bag_id
          WHERE b.flight_no = f.flight_no)                                 AS scan_count
FROM flight f;
```

Same correctness guarantee, sometimes a clearer mental model for 2-3
metrics, but doesn't scale well past a handful of correlated subqueries —
prefer the CTE form once you're past 3-4 metrics, since the optimizer can
usually plan it as a single pass with hash aggregates rather than N
independent subquery executions.

---

## Batch vs Streaming Processing

If `bag_scan_event` is high-volume (streamed from scanners in real time),
don't run the fan-out-prone join against the live table for a dashboard —
maintain `scan_agg` as a **materialized/summary table** updated
incrementally (on insert, `scan_count = scan_count + 1` for that flight, or
via the counter-sharding pattern from
[01](./01-Hot-Row-Contention-and-Counter-Sharding.md) if scan volume per
flight is itself high). The CTE form above is for on-demand/batch reporting
queries; a live operational dashboard wants pre-aggregated state, not a
join computed on every page load.

---

## Hot-Key Mitigation

A flight with an unusually high scan count (a single bag re-scanned
repeatedly due to a routing exception) can dominate `scan_agg`'s
aggregation cost for that one flight, similar in spirit to a hot row —
watch for a small number of `flight_no` values with pathologically high
`scan_count` and consider capping or separately flagging "exception" scan
events rather than letting them balloon the normal operational count.

---

## Observability & Metrics

- The tell-tale sign of a fan-out bug already in production: a metric that
  is a suspiciously round multiple of what's expected (e.g. total weight
  reported as exactly 3x actual — every bag happened to average 3 scans).
- Add a regression test that seeds one entity with an *uneven* number of
  child rows on each side (e.g. one bag with 5 scans, another with 1) and
  asserts both aggregates independently — fan-out bugs often pass tests
  that use uniform fixture data (e.g. every bag has exactly 2 scans) because
  the multiplication factor is constant and gets absorbed into a "close
  enough" assertion.

---

## Failure Scenarios

- **Silent wrong numbers, no error** — this bug never throws; it just
  under- or over-reports, often only enough to look plausible. Treat any
  multi-relationship aggregation query as needing an explicit fan-out
  review, not just a correctness review of the `WHERE` clause.
- **Query added later, existing query "helpfully" reused** — someone joins
  a new "many" table onto an existing query that already had one "many"
  join, without noticing the existing aggregates are now wrong. Code review
  checklist: any time a join is added to a query that already contains a
  `GROUP BY`/aggregate, re-derive whether every aggregate column is still
  correct at the new join's grain.

---

## Enterprise Mapping

This shows up anywhere one parent entity has multiple independent
one-to-many children being reported together: an order with line items and
separately with payment attempts; a customer with addresses and separately
with support tickets; a flight with bags and separately with crew
assignments. Any "give me counts/sums across two child relationships in one
row per parent" report is a fan-out risk by default.

---

## Java / Spring Boot Implementation Ideas

```java
public record FlightBagSummary(
    String flightNo, long bagCount, BigDecimal totalWeight, long scanCount) {}

@Repository
public class FlightBagSummaryRepository {

    private final JdbcTemplate jdbc;

    public List<FlightBagSummary> summarize(List<String> flightNos) {
        String sql = """
            WITH bag_agg AS (
                SELECT flight_no, COUNT(*) AS bag_count, SUM(weight_kg) AS total_weight
                FROM bag_detail WHERE flight_no = ANY(?)
                GROUP BY flight_no
            ),
            scan_agg AS (
                SELECT b.flight_no, COUNT(*) AS scan_count
                FROM bag_scan_event s
                JOIN bag_detail b ON b.bag_id = s.bag_id
                WHERE b.flight_no = ANY(?)
                GROUP BY b.flight_no
            )
            SELECT f.flight_no, ba.bag_count, ba.total_weight, sa.scan_count
            FROM UNNEST(?) AS f(flight_no)
            LEFT JOIN bag_agg ba ON ba.flight_no = f.flight_no
            LEFT JOIN scan_agg sa ON sa.flight_no = f.flight_no
            """;
        Array flightArray = jdbc.getDataSource().getConnection()
            .createArrayOf("varchar", flightNos.toArray());
        return jdbc.query(sql, summaryRowMapper, flightArray, flightArray, flightArray);
    }
}
```

Note the batch-key pattern from the SQL fundamentals case study
([sql/04](../04-conditional-aggregation-case-study.md)) composes directly
with this one: the `WHERE flight_no = ANY(?)` batch filter and the
aggregation-fence CTEs solve two different problems (N+1 round trips vs.
row multiplication) and are meant to be used together, not as alternatives.

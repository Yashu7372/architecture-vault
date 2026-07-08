# Case Study: Bag Counts for 50 Random Flights

## Source

- Own work scenario (baggage/reporting system)

## Problem

Given a batch of ~50 random flights (`flight_no`, `flight_date`, `origin`),
get per-flight counts of total bags, loaded bags, not-loaded bags, offloaded
bags, and rush bags — without joining on some fixed set of conditions and
without issuing one query per flight.

---

## The Brute-Force Approach (What Not To Do)

```java
for (Flight f : flights) { // 50 flights
    int total = jdbcTemplate.queryForObject(
        "SELECT COUNT(*) FROM bag_detail WHERE flight_no=? AND flight_date=? AND origin=?",
        Integer.class, f.getFlightNo(), f.getFlightDate(), f.getOrigin());
    int loaded = jdbcTemplate.queryForObject(
        "SELECT COUNT(*) FROM bag_detail WHERE flight_no=? AND flight_date=? AND origin=? AND loaded_flag='Y'",
        Integer.class, f.getFlightNo(), f.getFlightDate(), f.getOrigin());
    // ...repeat for not_loaded, offloaded, rush
}
```

- 50 flights × 5 counts = up to **250 round trips** to the database.
- Each round trip pays network latency + parse/plan overhead independently.
- The DB never sees the full picture, so it can't optimize across flights.

---

## The Set-Based Approach

```sql
SELECT
    flight_no,
    flight_date,
    origin,
    COUNT(*)                                            AS total_bags,
    SUM(CASE WHEN loaded_flag  = 'Y' THEN 1 ELSE 0 END) AS loaded_bags,
    SUM(CASE WHEN loaded_flag  = 'N' THEN 1 ELSE 0 END) AS not_loaded_bags,
    SUM(CASE WHEN offload_flag = 'Y' THEN 1 ELSE 0 END) AS offloaded_bags,
    SUM(CASE WHEN rush_flag    = 'Y' THEN 1 ELSE 0 END) AS rush_bags
FROM bag_detail
WHERE (flight_no, flight_date, origin) IN (
    ('EK001', DATE '2026-07-07', 'DXB'),
    ('EK002', DATE '2026-07-07', 'DXB')
    -- ...up to 50 tuples, bound in from Java
)
GROUP BY flight_no, flight_date, origin;
```

- **1 round trip** for all 50 flights, all 5 metrics.
- Every "count" collapses into one `SUM(CASE WHEN ...)` column computed in
  the same pass over the rows — no repeated scans.
- With `idx_bag_detail_flight (flight_no, flight_date, origin)` in place,
  the engine can do 50 fast index lookups (or one hash join against the
  values list) instead of 250 separate query executions.

---

## Data Flow

1. Java layer builds the list of 50 `(flight_no, flight_date, origin)` keys
   the report needs.
2. Keys are bound into a single parameterized query — tuple `IN` for small
   batches, or a `VALUES` list joined against for larger ones (see
   [03](./03-optimization-techniques.md#technique-3--join-against-a-values-list--temp-table-for-large-batches)).
3. Database does one pass over `bag_detail` filtered by the composite index,
   grouping and conditionally summing in the same scan.
4. One result set comes back — one row per flight, all counts already
   computed. Java just maps rows to a DTO.

---

## Tradeoffs

**Conditional aggregation (this approach)**
- Advantages: one round trip, one execution plan, index-friendly, scales to
  hundreds of flights without code changes.
- Disadvantages: query gets wider as more flag columns are added; very
  large key lists (thousands) need the `VALUES`-join variant instead of a
  literal `IN` list.

**Per-flight queries (brute force)**
- Advantages: simple to write, easy to reason about one flight at a time.
- Disadvantages: N× round trips, N× parse/plan overhead, doesn't scale,
  hides the real cost until load testing.

---

## Interview Questions

- Why is `SUM(CASE WHEN ...)` faster than five separate `COUNT(*) WHERE ...`
  queries per flight?
- What index makes the tuple `IN` / join lookup efficient here, and why
  does column order matter?
- At what batch size would you switch from a literal `IN (...)` list to a
  `VALUES` + `JOIN`, and why?
- How would this query's plan change if `flight_date` had very low
  cardinality (e.g. only 3 distinct dates in the table)?

---

## My Thoughts

- This is the general shape of "I have a batch of keys, I need aggregated
  metrics per key" — applies far beyond baggage: order counts per
  customer, event counts per device, transaction counts per account, etc.
- The Java-side fix is as important as the SQL fix: build the key list once,
  bind it as a batch parameter, and stop writing loops around single-row
  queries.

# How SQL Parsing & Execution Works

## Source

- Use The Index, Luke
- Ask TOM / Oracle Docs
- Modern SQL by Markus Winand

---

## Problem

SQL reads top-to-bottom (`SELECT ... FROM ... WHERE ... GROUP BY ...`), but
the database does **not** execute it in that order, and it doesn't execute
your text directly at all — it goes through several stages first. Not
knowing this leads to confusion about why a `WHERE` clause can't reference a
`SELECT` alias, why `GROUP BY` runs before `HAVING`, and why the same query
can suddenly get slow after a data change (a new execution plan gets chosen).

---

## The Pipeline (Parser → Executor)

1. **Parsing (Syntax Analysis)**
   - The SQL text is tokenized and checked against grammar rules.
   - Produces a parse tree. Pure syntax check — doesn't know if tables/columns
     exist yet.

2. **Semantic Analysis / Binding**
   - Table and column names are resolved against the data dictionary/catalog.
   - Checks privileges, data types, ambiguous column references.
   - Produces a "bound"/logical query tree.

3. **Query Rewrite (Logical Optimization)**
   - View expansion, subquery unnesting, predicate pushdown, constant
     folding, `IN`-list to join transformations.
   - The optimizer rewrites the logical tree into an equivalent but
     potentially cheaper form — this is why two differently-written queries
     can end up with identical plans.

4. **Cost-Based Optimization (Physical Planning)**
   - The optimizer enumerates candidate execution strategies (which index to
     use, join order, join algorithm — nested loop / hash / merge) and
     estimates their cost using table/index statistics (row counts,
     histograms, cardinality estimates).
   - Picks the plan with the lowest estimated cost. This is why stale
     statistics cause bad plans even when the SQL hasn't changed.

5. **Execution Plan Generation**
   - The chosen strategy is compiled into a physical execution plan — a tree
     of operators (scan, filter, join, sort, aggregate).

6. **Execution**
   - The engine walks the plan tree, usually pulling rows lazily (iterator
     model: each operator calls `next()` on its children), and streams
     results back.

7. **(Optional) Plan Caching**
   - Many engines cache the parsed/optimized plan keyed by the query text
     (or a normalized form) so repeated executions skip steps 1–4. This is
     why prepared statements / bind variables matter — literal-embedded SQL
     defeats plan caching and causes "hard parsing" every time.

---

## Logical Processing Order (Not Execution Order, but the Order That Matters for Correctness)

```
FROM / JOIN
WHERE
GROUP BY
HAVING
SELECT (incl. window functions)
DISTINCT
ORDER BY
LIMIT / OFFSET / FETCH
```

This explains:
- Why you can't use a `SELECT` alias in `WHERE` (alias doesn't exist yet at
  that logical stage) but you *can* in `ORDER BY` (runs after `SELECT`).
- Why `WHERE` filters rows before grouping, while `HAVING` filters groups
  after aggregation.
- Why window functions (which conceptually run during/after `SELECT`) can
  see aggregated results but can't be referenced in the same `SELECT`'s
  `WHERE`.

The physical execution plan does **not** have to follow this order — the
optimizer is free to reorder/interleave operations as long as the result is
equivalent (e.g. pushing a `WHERE` predicate down into an index scan before
a join even happens).

---

## Interview Questions

- Why doesn't `WHERE` see column aliases from `SELECT`?
- What's the difference between a hard parse and a soft parse, and why does
  it matter for bind variables?
- Why can two logically-equivalent queries produce different execution
  plans?
- What causes a plan to flip after being stable for months? (stats update,
  data skew, parameter sniffing / bind variable peeking)

---

## My Thoughts

- Bind variables / prepared statements aren't just a security thing (SQL
  injection) — they also let the DB reuse parsed/optimized plans instead of
  hard-parsing every call.
- When a query "used to be fast and now isn't," check statistics freshness
  and row-count growth before touching the SQL itself.

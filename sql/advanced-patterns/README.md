# Advanced Patterns — DB & Query Optimization Deep Dives

Staff/principal-depth write-ups of hard, recurring database problems at
production scale. Each doc follows the same structure: problem evolution
(why the naive version breaks), production architecture, partitioning/
sharding, batch vs streaming, hot-key handling, observability, failure
scenarios, enterprise mapping, and Java/Spring Boot implementation ideas.

## Done

1. [Hot-Row Contention & Counter Sharding](./01-Hot-Row-Contention-and-Counter-Sharding.md)
2. [Deep Pagination: Keyset vs Offset](./02-Deep-Pagination-Keyset-vs-Offset.md)
3. [Fan-Out Joins & Aggregation Fences](./03-Fan-Out-Joins-and-Aggregation-Fences.md)

## Planned

4. Batch Key Lookups at Scale (large `IN` lists, temp-table joins, chunking)
5. Read/Write Segregation & Replica Lag
6. Plan Instability & Bind Variable Peeking
7. Partitioning & Partition Pruning
8. Optimistic vs Pessimistic Locking
9. Idempotent Writes & Dedup (unique constraints, `ON CONFLICT`, retries)
10. Window Functions for Latest-State Projections

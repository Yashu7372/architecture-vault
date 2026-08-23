# Architecture Vault

Architecture Vault is the **ingestion and retrieval knowledge layer** for the enterprise-AI portfolio build.

## Canonical branch

**`feature/portfolio-knowledge-source-of-truth`** is the fixed integration branch for this path. New collector, source-registry, scheduled-ingestion, retrieval-context, learning-course, and portfolio-knowledge changes should be made here first. Older feature branches are historical implementation lines and should not be treated as independent sources of truth.

## What this repository owns

Architecture Vault owns the left side of the portfolio knowledge flow:

```text
External engineering knowledge
  -> collect
  -> normalize
  -> deduplicate
  -> index
  -> chunk
  -> retrieve
  -> lightweight relationships
  -> bounded context packs
```

It intentionally does **not** own the final curated architecture graph, flagship application implementation, or public content publishing.

The complete portfolio connection is documented in [`PORTFOLIO_KNOWLEDGE_SYSTEM.md`](PORTFOLIO_KNOWLEDGE_SYSTEM.md).

## Canonical implementation

The active implementation lives under [`engineering-knowledge-base/`](engineering-knowledge-base/).

It already includes collectors for:

- curated catalogs;
- normal web/engineering articles;
- Substack publications and course curricula;
- GitHub repositories;
- arXiv research;
- PDFs/white papers;
- YouTube metadata;
- imported Chrome bookmarks.

It also includes the day-by-day SDCourse learning builder, context database, lightweight graph, query tool, tests, and GitHub Actions validation.

## One-command portfolio knowledge build

```bash
python engineering-knowledge-base/scripts/run_portfolio_knowledge_pipeline.py --group canonical-public --resume
```

Use `--list-groups` to see the supported source groups.

## Source-of-truth rule

Git stores collector code, source definitions, schemas/policies, original notes, curated learning material, and portfolio architecture. Raw third-party article captures and generated retrieval databases remain local/private and are rebuildable from the source registry.

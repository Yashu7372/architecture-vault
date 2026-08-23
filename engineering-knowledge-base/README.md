# Engineering Knowledge Base

A private-first collector, learning, and retrieval context layer for architecture articles, engineering blogs, GitHub repositories, Substack publications, YouTube videos, PDFs, white papers, and AI/LLM research.

## Portfolio role and source of truth

This directory is the active knowledge-layer implementation for the portfolio build. The canonical integration branch is:

`feature/portfolio-knowledge-source-of-truth`

Its responsibility is **discovery -> ingestion -> normalization -> retrieval -> learning support**. The curated semantic portfolio graph remains in `Yashu7372/enterprise-architecture-graph`, while implementation/verification evidence comes from flagship repositories such as `Yashu7372/engineering-control-plane`.

Read [`../PORTFOLIO_KNOWLEDGE_SYSTEM.md`](../PORTFOLIO_KNOWLEDGE_SYSTEM.md) before changing the boundaries.

All generated files remain inside this repository under `engineering-knowledge-base/output`. Generated third-party captures and retrieval databases are intentionally ignored by Git and should stay local/private.

## Canonical portfolio pipeline

Run the public source-of-truth pipeline with:

```bash
python engineering-knowledge-base/scripts/run_portfolio_knowledge_pipeline.py \
  --group canonical-public \
  --resume
```

List configured groups:

```bash
python engineering-knowledge-base/scripts/run_portfolio_knowledge_pipeline.py --list-groups
```

Validate the registry/contracts without network collection:

```bash
python engineering-knowledge-base/scripts/run_portfolio_knowledge_pipeline.py --validate-only
```

The canonical runner composes the existing collectors, index builder, and context builder instead of replacing them. Specialized catalog/Substack/course scripts remain available for focused workflows.

## What it produces

The pipeline turns source catalogs and individual links into:

1. Extracted Markdown notes with normalized metadata.
2. A deduplicated document manifest.
3. Per-source and master indexes.
4. Section-aware, overlapping retrieval chunks.
5. A SQLite context database with FTS5 full-text search.
6. A lightweight graph containing document, source, section, tag, and reference relationships.
7. Compact Markdown or JSON context packs for AI agents and engineering research.
8. Day-by-day course learning material with explicit public/preview/curriculum-only access boundaries.

## Supported source types

- `catalog` — a Markdown page containing many curated article links.
- `web` — company engineering blogs and normal article pages.
- `substack` — public/authenticated Substack pages with explicit access boundaries.
- `github` — README and important Markdown files from repositories.
- `arxiv` — research papers discovered from a query.
- `pdf` — local PDFs and white papers.
- `youtube` — video metadata, ready for transcript integration.

Source definitions live in `config/sources.manual.yaml` and `config/sources.generated.yaml`. Reusable execution groups live in `config/source-groups.yaml`.

## System Design Academy source

`sources.manual.yaml` includes the complete catalog from `systemdesign42/system-design-academy/README.md`.

The catalog collector:

- reads every Markdown article link;
- keeps the README section and subsection as source metadata;
- canonicalizes and deduplicates URLs;
- preserves every catalog location when one article appears in multiple sections;
- extracts each reachable article through the normal web collector;
- supports resumable collection for large catalogs.

## SDCourse learning source

The consolidated branch also contains the Substack course discovery, public-boundary collectors, resumable day-wise learning scheduler, course completion engine, first-five validation, and first-25 review-pack work from the earlier feature branches.

The day-wise runner remains:

```bash
python engineering-knowledge-base/scripts/run_daily_course_learning.py --track python-js
```

A local/private continuous run can use:

```bash
python engineering-knowledge-base/scripts/run_daily_course_learning.py \
  --track python-js \
  --daemon \
  --interval-hours 24
```

The repository default branch contains only a thin scheduled GitHub Actions shim. It checks out `feature/portfolio-knowledge-source-of-truth` so the feature branch remains the implementation authority while GitHub cron can actually execute.

## Installation

From the repository root:

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -r engineering-knowledge-base/requirements.txt
playwright install chromium
```

## Focused System Design Academy build

Run:

```bash
python engineering-knowledge-base/scripts/ingest_system_design_academy.py
```

For a small smoke test:

```bash
python engineering-knowledge-base/scripts/ingest_system_design_academy.py \
  --max-articles 5 \
  --skip-validation
```

Resume after interruption without recollecting completed article URLs:

```bash
python engineering-knowledge-base/scripts/ingest_system_design_academy.py --resume
```

The same flow can be executed step by step:

```bash
python engineering-knowledge-base/scripts/validate_catalog.py \
  --source system-design-academy

python engineering-knowledge-base/scripts/collect.py \
  --source system-design-academy \
  --resume

python engineering-knowledge-base/scripts/build_index.py
python engineering-knowledge-base/scripts/build_context.py
```

## Query the context layer

```bash
python engineering-knowledge-base/scripts/query_context.py \
  "idempotent payment processing and retry handling"
```

Filter by source or tag:

```bash
python engineering-knowledge-base/scripts/query_context.py \
  "event-driven read models and real-time UI updates" \
  --source system-design-academy

python engineering-knowledge-base/scripts/query_context.py \
  "multi-agent memory architecture" \
  --tag ai-engineering \
  --format json
```

The query command returns the most relevant chunks, source URLs, article headings, publication metadata, and tag-related documents. This output can be inserted into a task workspace or agent prompt as a bounded context pack.

## Generated structure

```text
engineering-knowledge-base/
├── collectors/
├── config/
│   ├── sources.manual.yaml
│   ├── sources.generated.yaml
│   └── source-groups.yaml
├── learning/
├── scripts/
├── tests/
└── output/
    ├── notes/
    ├── indexes/
    ├── reports/
    ├── courses/
    ├── daily-learning/
    ├── scheduler/
    ├── manifest.json
    ├── MASTER_INDEX.md
    └── context/
        ├── context.sqlite
        ├── chunks.jsonl
        ├── graph.json
        └── CONTEXT_INDEX.md
```

The SQLite database contains:

- `documents` — canonical document metadata and note locations;
- `chunks` — section-aware retrieval units;
- `chunks_fts` — FTS5 index, with a normal-table fallback when FTS5 is unavailable;
- `tags` — document-to-topic mappings;
- `relationships` — `FROM_SOURCE`, `IN_SECTION`, `TAGGED_WITH`, and `REFERENCES` edges.

## Validation and tests

Validate every unique catalog URL and generate JSON/Markdown health reports:

```bash
python engineering-knowledge-base/scripts/validate_catalog.py \
  --source system-design-academy \
  --fail-on-error
```

Run the unit tests:

```bash
python -m unittest discover \
  -s engineering-knowledge-base/tests \
  -p "test_*.py"
```

The source-of-truth tests verify collector coverage, source-group integrity, scheduled-public boundaries, and the portfolio graph connection.

## Privacy and publishing rule

Extracted article content and generated databases are intentionally ignored by Git. Keep those artifacts local or in private runtime/cache storage. A public repository should contain only ingestion code, source links, public metadata when appropriate, your own summaries, diagrams, original analysis, and original learning material—not copied full-text articles.

Promotion into the public `enterprise-architecture-graph` must be a reviewed/original synthesis with provenance, relationships, trade-offs, maturity, and implementation/evidence links.

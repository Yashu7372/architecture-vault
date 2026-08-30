# Engineering Knowledge Base

A private-first collector, learning, and retrieval context layer for architecture articles, engineering blogs, GitHub repositories, Substack publications, YouTube videos, PDFs, white papers, and AI/LLM research.

## Portfolio role and source of truth

This directory is the active knowledge-layer implementation for the portfolio build. The canonical integration branch is:

`feature/portfolio-knowledge-source-of-truth`

Its responsibility is **discovery -> ingestion -> normalization -> retrieval -> learning support**. The curated semantic portfolio graph remains in `Yashu7372/enterprise-architecture-graph`, while implementation/verification evidence comes from flagship repositories such as `Yashu7372/engineering-control-plane`.

Read [`../PORTFOLIO_KNOWLEDGE_SYSTEM.md`](../PORTFOLIO_KNOWLEDGE_SYSTEM.md) before changing the boundaries. For the Enterprise OS capability/runtime boundary and safe run commands, read [`ENTERPRISE_OS_CAPABILITIES.md`](ENTERPRISE_OS_CAPABILITIES.md).

All generated files remain inside this repository under `engineering-knowledge-base/output`. Generated third-party captures, capability evidence, refresh deltas/state, and retrieval databases are intentionally ignored by Git and should stay local/private.

## Enterprise OS capability model

Collectors are now first-class **Capability Plane** primitives declared in `config/capabilities.yaml`:

- `vault.collect.web`
- `vault.collect.catalog`
- `vault.collect.substack`
- `vault.collect.github`
- `vault.collect.arxiv`
- `vault.collect.pdf`
- `vault.collect.youtube`

Collector capabilities are read/acquisition-only. They cannot externally write, promote canonical knowledge, or choose another capability dynamically. External content crosses an `UNTRUSTED_EXTERNAL` boundary and remains data rather than instructions. Reusable protocol/library mechanics live under `drivers/`, so one capability does not import another capability's internal implementation.

Architecture Vault can execute these capabilities locally today. A future Enterprise OS Control Plane can discover the same manifests and own authorization, scheduling, execution-provider selection, resource policy, and cross-project run state without changing collector implementations.

Validate these contracts without network access:

```bash
python engineering-knowledge-base/scripts/validate_capabilities.py --json
python engineering-knowledge-base/scripts/run_portfolio_knowledge_pipeline.py --validate-only
```

## Canonical portfolio pipeline

Run the public source-of-truth pipeline with:

```bash
python engineering-knowledge-base/scripts/run_portfolio_knowledge_pipeline.py \
  --group canonical-public \
  --resume
```

For a safe first capability run that does not replace the local manifest/context:

```bash
python engineering-knowledge-base/scripts/run_portfolio_knowledge_pipeline.py \
  --source portfolio-enterprise-architecture-graph \
  --dry-run \
  --strict
```

List configured groups:

```bash
python engineering-knowledge-base/scripts/run_portfolio_knowledge_pipeline.py --list-groups
```

The canonical runner composes capability execution, evidence capture, index building, context building, and deterministic change evaluation. Specialized catalog/Substack/course scripts remain available for focused workflows.

## What it produces

The pipeline turns source catalogs and individual links into:

1. Extracted Markdown notes with normalized metadata and trust/capability provenance.
2. A last-good-snapshot-preserving document manifest.
3. Per-source and master indexes.
4. Meaningful, section-aware retrieval chunks.
5. A schema-v3 SQLite context database with FTS5 full-text search.
6. A lightweight evidence graph containing document, source, capability, section, tag, reference, and candidate concept relationships.
7. Deterministic source-authority scores and duplicate evidence units.
8. Evidence-backed extracted concept candidates and deterministic inferred-relation candidates.
9. Multi-lens extractive candidate learning units.
10. Incremental source state and candidate knowledge deltas for targeted downstream re-evaluation.
11. Compact Markdown or JSON context packs that fence external excerpts as untrusted evidence.
12. Day-by-day course learning material with explicit public/preview/curriculum-only access boundaries.

A failed collector does not erase the previous good source snapshot. `ADDED`, `CONTENT_CHANGED`, `METADATA_CHANGED`, and `REMOVED` deltas are always `CANDIDATE_ONLY`; they never auto-promote knowledge.

## Supported source types

- `catalog` — a Markdown page containing many curated article links.
- `web` — company engineering blogs and normal article pages.
- `substack` — public/authenticated Substack pages with explicit access boundaries.
- `github` — README and important Markdown files from repositories.
- `arxiv` — research papers discovered from a query.
- `pdf` — local PDFs and white papers.
- `youtube` — video metadata/transcript evidence where available.

Source definitions live in `config/sources.manual.yaml` and `config/sources.generated.yaml`. Reusable execution groups live in `config/source-groups.yaml`.

## System Design Academy source

`sources.manual.yaml` includes the complete catalog from `systemdesign42/system-design-academy/README.md`.

The catalog capability:

- reads every Markdown article link;
- keeps the README section and subsection as source metadata;
- canonicalizes and deduplicates URLs;
- preserves every catalog location when one article appears in multiple sections;
- uses the shared web resource driver for target-page extraction;
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

The repository default branch contains only a thin scheduled GitHub Actions shim. It checks out `feature/portfolio-knowledge-source-of-truth` so the feature branch remains the implementation authority while GitHub cron can execute.

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

Filter by source, tag, or extracted taxonomy concept:

```bash
python engineering-knowledge-base/scripts/query_context.py \
  "event-driven read models and real-time UI updates" \
  --source system-design-academy

python engineering-knowledge-base/scripts/query_context.py \
  "multi-agent memory architecture" \
  --tag ai-engineering \
  --format json

python engineering-knowledge-base/scripts/query_context.py \
  "duplicate processing and retry" \
  --concept idempotency
```

The query command returns bounded evidence with source URL, authority tier/score, collector capability, trust boundary, evidence unit, article heading, and extracted concept candidates. External excerpts are fenced as `UNTRUSTED_SOURCE_EVIDENCE` before they are suitable for an LLM/task context.

## Generated structure

```text
engineering-knowledge-base/
├── capabilities/
├── collectors/
├── drivers/
├── processing/
├── config/
│   ├── capabilities.yaml
│   ├── sources.manual.yaml
│   ├── sources.generated.yaml
│   ├── source-groups.yaml
│   ├── knowledge-taxonomy.yaml
│   ├── evidence-policy.yaml
│   └── learning-lenses.yaml
├── learning/
├── scripts/
├── tests/
└── output/
    ├── notes/
    ├── indexes/
    ├── reports/
    ├── evidence/<run-id>/
    ├── deltas/<run-id>.json
    ├── deltas/latest.json
    ├── state/source-state.json
    ├── courses/
    ├── daily-learning/
    ├── scheduler/
    ├── manifest.json
    ├── MASTER_INDEX.md
    └── context/
        ├── context.sqlite
        ├── chunks.jsonl
        ├── graph.json
        ├── concepts.json
        ├── relations.json
        ├── duplicates.json
        ├── learning-units.json
        ├── quality-report.json
        └── CONTEXT_INDEX.md
```

The schema-v3 SQLite database contains:

- `documents` — canonical document metadata, capability/trust provenance, source authority, and evidence-unit identity;
- `chunks` — meaningful section-aware retrieval units with extractive gists;
- `chunks_fts` — FTS5 index, with a normal-table fallback when FTS5 is unavailable;
- `tags` and `relationships` — source/reference/tag/capability graph edges;
- `duplicate_evidence` — duplicate clusters so copies do not inflate evidence;
- `concepts` and `chunk_concepts` — taxonomy plus `EXTRACTED` concept candidates;
- `inferred_relations` — deterministic statistical `INFERRED` relation candidates;
- `learning_units` — extractive multi-lens candidate learning units;
- `knowledge_deltas` — latest targeted re-evaluation hints.

## Validation and tests

Validate every unique catalog URL and generate JSON/Markdown health reports:

```bash
python engineering-knowledge-base/scripts/validate_catalog.py \
  --source system-design-academy \
  --fail-on-error
```

Run the offline capability validation and unit tests:

```bash
python engineering-knowledge-base/scripts/validate_capabilities.py --json

python -m unittest discover \
  -s engineering-knowledge-base/tests \
  -p "test_*.py"
```

CI compiles all Python sources, validates collector capability contracts, validates the canonical pipeline registry, and runs the complete test suite.

## Privacy and publishing rule

Extracted article content, generated capability evidence, deltas/state, and retrieval databases are intentionally ignored by Git. Keep those artifacts local or in private runtime/cache storage. A public repository should contain only ingestion code, source links, public metadata when appropriate, your own summaries, diagrams, original analysis, and original learning material—not copied full-text articles.

Promotion into the public `enterprise-architecture-graph` must be a reviewed/original synthesis with provenance, relationships, trade-offs, maturity, and implementation/evidence links. Collector capabilities and candidate deltas never perform that promotion themselves.

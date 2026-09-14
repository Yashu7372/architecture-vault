# Engineering Knowledge Base

A private-first collector and retrieval context layer for architecture articles, engineering blogs, GitHub repositories, Substack publications, YouTube videos, PDFs, white papers, and AI/LLM research.

All generated files remain inside this repository under `engineering-knowledge-base/output`. This implementation does not read from or write to `~/.dnbms`, `ai-control-plane`, or any external agent-memory directory.

## What it produces

The pipeline turns source catalogs and individual links into:

1. Extracted Markdown notes with normalized metadata.
2. A deduplicated document manifest.
3. Per-source and master indexes.
4. Section-aware, overlapping retrieval chunks.
5. A SQLite context database with FTS5 full-text search.
6. A lightweight graph containing document, source, section, tag, and reference relationships.
7. Compact Markdown or JSON context packs for AI agents and engineering research.

## Supported source types

- `catalog` — a Markdown page containing many curated article links.
- `web` — company engineering blogs and normal article pages.
- `substack` — public or authenticated Substack pages.
- `github` — README and important Markdown files from repositories.
- `arxiv` — research papers discovered from a query.
- `pdf` — local PDFs and white papers.
- `youtube` — video metadata, ready for transcript integration.

## System Design Academy source

`sources.manual.yaml` includes the complete catalog from:

- `systemdesign42/system-design-academy/README.md`

The catalog collector:

- reads every Markdown article link;
- keeps the README section and subsection as source metadata;
- canonicalizes and deduplicates URLs;
- preserves every catalog location when one article appears in multiple sections;
- extracts each reachable article through the normal web collector;
- supports resumable collection for large catalogs.

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

## Build the complete context layer

Run the one-command pipeline:

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

The query command returns the most relevant chunks, source URLs, article headings, publication metadata, and tag-related documents. This output can be inserted directly into a task workspace or an agent prompt as a bounded context pack.

## Generated structure

```text
engineering-knowledge-base/
├── collectors/
├── config/
├── scripts/
├── tests/
└── output/
    ├── notes/
    ├── indexes/
    ├── reports/
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

## Privacy and publishing rule

Extracted article content and generated databases are intentionally ignored by Git. Keep those artifacts local or in a private storage location. A public repository should contain only the ingestion code, source links, your own summaries, diagrams, and original analysis—not copied full-text articles.

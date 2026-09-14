# Engineering Knowledge Base

A private-first engineering brain for architecture articles, company engineering blogs, GitHub repositories, Substack courses, YouTube videos, PDFs, whitepapers, and AI/LLM research papers.

## Goal

Turn scattered links into traceable, reusable engineering knowledge:

1. Capture exact links or discover sources
2. Extract source content deterministically
3. Preserve raw source evidence separately
4. Create AI-ready analysis packets
5. Validate structured AI analysis
6. Generate 10-minute digests, concepts, patterns, and graph relationships
7. Reuse accepted knowledge for learning, portfolio content, and engineering task context

## Architecture

```text
inbox/inbox.md
      |
      v
source router
      |
      v
source-specific collectors
      |
      v
output/raw/                     <- source evidence
      |
      v
output/analysis-packets/        <- provider-neutral AI request contract
      |
      v
AI reasoning                    <- ChatGPT/API/other model
      |
      v
analysis-result.schema.json
      |
      v
validated deterministic writer
      |
      +--> output/digests/
      +--> output/concepts/
      +--> output/patterns/
      +--> output/graph/relationships.jsonl
```

Raw extraction and AI interpretation are deliberately separated. Generated knowledge must remain traceable to the source that contributed it.

## Supported source types

- `web` - normal article pages; supports `mode: exact` for a user-selected URL and `mode: discover` for site discovery
- `substack` - public or logged-in Substack pages using Playwright
- `github` - README and important architecture/design/docs markdown files
- `arxiv` - research-paper feeds/queries
- `pdf` - local or remote PDF/whitepaper files with page boundaries
- `youtube` - transcript extraction when captions are available

## Inbox workflow

Paste as many links as you want into `inbox/inbox.md`:

```markdown
- [ ] https://example.com/article
- [ ] https://github.com/org/repo
- [ ] https://youtube.com/watch?v=...
- [ ] https://example.com/paper.pdf
```

Every link is processed independently and tracked in `output/state/inbox-state.json`. One failed link does not invalidate the rest of the batch.

Run:

```bash
python engineering-knowledge-base/scripts/process_inbox.py
```

Retry only failed sources:

```bash
python engineering-knowledge-base/scripts/process_inbox.py --retry-failed
```

Successful extraction produces:

```text
output/raw/<source-id>-<title>.md
output/analysis-packets/<source-id>.json
```

The analysis packet is intentionally model-provider neutral. It can be analyzed manually in ChatGPT today and by an API/agent later without changing the collector or storage model.

## Applying AI analysis

AI analysis must follow:

`schemas/analysis-result.schema.json`

Place a conforming result in a local JSON file and run:

```bash
python engineering-knowledge-base/scripts/apply_analysis.py path/to/analysis-result.json
```

The deterministic writer then creates or updates:

- `output/digests/` - source-specific 10-minute engineering reads
- `output/concepts/` - reusable concept knowledge with source contributions
- `output/patterns/` - reusable engineering patterns with source evidence
- `output/graph/relationships.jsonl` - deduplicated source-backed relationships

## Existing discovery workflow

The original configured-source workflow remains available:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r engineering-knowledge-base/requirements.txt
playwright install chromium

python engineering-knowledge-base/scripts/import_chrome_bookmarks.py
python engineering-knowledge-base/scripts/collect.py
python engineering-knowledge-base/scripts/build_index.py
```

## Design rules

- Capture in bulk; process each source independently.
- Deterministic code performs extraction, validation, state tracking, persistence, and deduplication.
- AI performs explanation, synthesis, concept discovery, pattern discovery, and relevance reasoning.
- Keep raw source evidence separate from generated knowledge.
- Do not silently replace or overwrite evidence with AI summaries.
- Every reusable concept, pattern, and relationship should retain source provenance.
- The knowledge model must not depend on a single AI vendor.

## Privacy rule

Keep full extracted source content private when licensing/copyright requires it. If publishing portfolio content, publish your own summaries, diagrams, implementation learnings, and source links rather than republishing complete source material.

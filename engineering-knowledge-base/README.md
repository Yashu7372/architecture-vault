# Engineering Knowledge Base

A private-first knowledge collector for architecture articles, company engineering blogs, GitHub repositories, Substack courses, YouTube videos, PDFs, whitepapers, and AI/LLM research papers.

## Goal

Turn scattered links into structured architecture notes:

1. Source discovery
2. Content extraction
3. Normalized metadata
4. Markdown notes
5. Topic indexes
6. Enterprise architecture learnings

## Supported source types

- `web` - company engineering blogs and normal article pages
- `substack` - logged-in Substack course/publication pages
- `github` - README and important markdown files from repositories
- `arxiv` - latest papers by query
- `pdf` - local PDF or whitepaper files
- `youtube` - video URL metadata placeholder for transcript integration

## Recommended flow

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r engineering-knowledge-base/requirements.txt
playwright install chromium

python engineering-knowledge-base/scripts/import_chrome_bookmarks.py
python engineering-knowledge-base/scripts/collect.py
python engineering-knowledge-base/scripts/build_index.py
```

## Privacy rule

Keep full extracted content in a private repo. If you ever make notes public, publish only your own summaries, diagrams, and source links.

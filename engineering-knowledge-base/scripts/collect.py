from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import sys

import yaml
from slugify import slugify

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collectors.arxiv_collector import ArxivCollector
from collectors.catalog_collector import CatalogCollector
from collectors.github_collector import GitHubCollector
from collectors.pdf_collector import PdfCollector
from collectors.substack_collector import SubstackCollector
from collectors.web_collector import WebCollector
from collectors.youtube_collector import YouTubeCollector

CONFIG_FILES = [ROOT / "config" / "sources.manual.yaml", ROOT / "config" / "sources.generated.yaml"]
OUTPUT_DIR = ROOT / "output"
NOTES_DIR = OUTPUT_DIR / "notes"
INDEX_DIR = OUTPUT_DIR / "indexes"
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"

NOTES_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)


def get_collector(source_type: str):
    collectors = {
        "web": WebCollector(),
        "catalog": CatalogCollector(),
        "substack": SubstackCollector(),
        "github": GitHubCollector(),
        "arxiv": ArxivCollector(),
        "pdf": PdfCollector(),
        "youtube": YouTubeCollector(),
    }
    if source_type not in collectors:
        raise ValueError(f"Unsupported source type: {source_type}")
    return collectors[source_type]


def digest(value: str, length: int = 12) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def document_id(doc) -> str:
    return f"doc-{digest(doc.url, 16)}"


def write_note(doc):
    folder = NOTES_DIR / slugify(doc.source_name)
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{slugify(doc.title)[:90]}-{digest(doc.url)}.md"
    path = folder / filename
    tags = ", ".join(doc.tags)
    metadata_json = json.dumps(doc.metadata, indent=2, ensure_ascii=False, sort_keys=True)
    content = f"""# {doc.title}

## Metadata

- Document ID: {document_id(doc)}
- Source Name: {doc.source_name}
- Source Type: {doc.source_type}
- URL: {doc.url}
- Author: {doc.author or ""}
- Published Date: {doc.published_date or ""}
- Tags: {tags}

### Source Context

```json
{metadata_json}
```

---

## Extracted Content

{doc.content}

---

## My Architecture Notes

### Problem Being Solved

### Existing Pain / Limitation

### New Architecture

### Main Components

| Component | Responsibility |
|---|---|
| | |

### Data Flow

1.
2.
3.

### Scaling Strategy

### Failure Handling

### Observability

### Security / Governance

### Trade-offs

| Benefit | Cost |
|---|---|
| | |

### Enterprise Application

- Domain entities, assets, or resources:
- Event stream / message broker:
- Cache / state store:
- Relational database / fallback store:
- Multi-tenant, station, or region model:
- Real-time dashboard / notification flow:
- AI agents / RAG / workflow automation:

### Final Summary In My Words

"""
    path.write_text(content, encoding="utf-8")
    return path


def load_sources() -> list[dict]:
    sources = []
    for file in CONFIG_FILES:
        if file.exists():
            data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
            sources.extend(data.get("sources", []))
    return sources


def load_existing_manifest() -> list[dict]:
    if not MANIFEST_FILE.exists():
        return []
    return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))


def write_source_index(source_name: str, items: list[dict]):
    index_file = INDEX_DIR / f"{slugify(source_name)}.md"
    lines = [
        f"# {source_name}",
        "",
        "| No | Title | Section | Type | Date | Tags | Notes |",
        "|---:|---|---|---|---|---|---|",
    ]
    for index, item in enumerate(items, start=1):
        tags = ", ".join(item.get("tags", []))
        section = item.get("metadata", {}).get("catalog_section", "")
        lines.append(
            f"| {index} | [{item['title']}]({item['url']}) | {section} | "
            f"{item['source_type']} | {item.get('published_date') or ''} | {tags} | "
            f"[{item['note_file']}]({item['note_file']}) |"
        )
    index_file.write_text("\n".join(lines), encoding="utf-8")


def parse_args():
    parser = ArgumentParser(description="Collect engineering knowledge sources into normalized Markdown notes.")
    parser.add_argument("--source", action="append", help="Collect only the named source. Repeat for multiple sources.")
    parser.add_argument("--resume", action="store_true", help="Skip URLs already present in the manifest.")
    parser.add_argument("--max-articles", type=int, help="Override max_articles for selected sources.")
    parser.add_argument("--list-sources", action="store_true", help="Print configured sources and exit.")
    return parser.parse_args()


def main():
    args = parse_args()
    all_sources = load_sources()
    if args.list_sources:
        for source in all_sources:
            print(f"{source['name']}\t{source['type']}")
        return

    selected_names = set(args.source or [])
    configured_names = {source["name"] for source in all_sources}
    missing_names = selected_names - configured_names
    if missing_names:
        raise ValueError(f"Unknown source(s): {', '.join(sorted(missing_names))}")
    sources = [source for source in all_sources if not selected_names or source["name"] in selected_names]

    existing = load_existing_manifest()
    if args.resume:
        manifest_by_url = {item["url"]: item for item in existing}
    elif selected_names:
        manifest_by_url = {
            item["url"]: item for item in existing if item.get("source_name") not in selected_names
        }
    else:
        manifest_by_url = {}

    collected_at = datetime.now(timezone.utc).isoformat()
    for configured_source in sources:
        source = dict(configured_source)
        if args.max_articles is not None:
            source["max_articles"] = args.max_articles
        existing_source_items = [
            item for item in manifest_by_url.values() if item.get("source_name") == source["name"]
        ]
        if args.resume and existing_source_items:
            source["skip_urls"] = [item["url"] for item in existing_source_items]

        print(f"Collecting: {source['name']} ({source['type']})")
        collector = get_collector(source["type"])
        try:
            docs = collector.collect(source)
        except Exception as exc:
            print(f"Failed source {source['name']}: {exc}")
            docs = []

        source_items = list(existing_source_items) if args.resume else []
        for doc in docs:
            note_path = write_note(doc)
            item = {
                "document_id": document_id(doc),
                "title": doc.title,
                "url": doc.url,
                "source_name": doc.source_name,
                "source_type": doc.source_type,
                "author": doc.author,
                "published_date": doc.published_date,
                "collected_at": collected_at,
                "content_hash": digest(doc.content, 32),
                "tags": doc.tags,
                "links": doc.links,
                "metadata": doc.metadata,
                "note_file": str(note_path.relative_to(OUTPUT_DIR)),
            }
            manifest_by_url[doc.url] = item
            source_items = [existing_item for existing_item in source_items if existing_item["url"] != doc.url]
            source_items.append(item)
            print(f"Saved: {doc.title}")

        source_items.sort(key=lambda item: item.get("metadata", {}).get("catalog_order", 10**9))
        write_source_index(source["name"], source_items)

    manifest = sorted(
        manifest_by_url.values(),
        key=lambda item: (
            item.get("source_name", ""),
            item.get("metadata", {}).get("catalog_order", 10**9),
            item.get("title", ""),
        ),
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Done. Total documents in manifest: {len(manifest)}")
    print(f"Output root: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

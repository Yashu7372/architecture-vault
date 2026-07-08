from pathlib import Path
import hashlib
import json
import sys
import yaml
from slugify import slugify

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collectors.web_collector import WebCollector
from collectors.substack_collector import SubstackCollector
from collectors.github_collector import GitHubCollector
from collectors.arxiv_collector import ArxivCollector
from collectors.pdf_collector import PdfCollector
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
        "substack": SubstackCollector(),
        "github": GitHubCollector(),
        "arxiv": ArxivCollector(),
        "pdf": PdfCollector(),
        "youtube": YouTubeCollector(),
    }
    if source_type not in collectors:
        raise ValueError(f"Unsupported source type: {source_type}")
    return collectors[source_type]


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def write_note(doc):
    folder = NOTES_DIR / slugify(doc.source_name)
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{slugify(doc.title)[:90]}-{digest(doc.url)}.md"
    path = folder / filename
    tags = ", ".join(doc.tags)
    content = f"""# {doc.title}

## Metadata

- Source Name: {doc.source_name}
- Source Type: {doc.source_type}
- URL: {doc.url}
- Author: {doc.author or ""}
- Published Date: {doc.published_date or ""}
- Tags: {tags}

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

- DNBMS:
- Solace / Kafka:
- Couchbase / Redis:
- Oracle / Postgres:
- SSE / real-time dashboard:
- AI agents / RAG:

### Final Summary In My Words

"""
    path.write_text(content, encoding="utf-8")
    return path


def load_sources():
    sources = []
    for file in CONFIG_FILES:
        if file.exists():
            data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
            sources.extend(data.get("sources", []))
    return sources


def write_source_index(source_name: str, items: list[dict]):
    index_file = INDEX_DIR / f"{slugify(source_name)}.md"
    lines = [
        f"# {source_name}",
        "",
        "| No | Title | Type | Date | Tags | Notes |",
        "|---:|---|---|---|---|---|",
    ]
    for index, item in enumerate(items, start=1):
        tags = ", ".join(item.get("tags", []))
        lines.append(f"| {index} | [{item['title']}]({item['url']}) | {item['source_type']} | {item.get('published_date') or ''} | {tags} | [{item['note_file']}]({item['note_file']}) |")
    index_file.write_text("\n".join(lines), encoding="utf-8")


def main():
    manifest = []
    for source in load_sources():
        print(f"Collecting: {source['name']} ({source['type']})")
        collector = get_collector(source["type"])
        try:
            docs = collector.collect(source)
        except Exception as exc:
            print(f"Failed source {source['name']}: {exc}")
            docs = []
        source_items = []
        for doc in docs:
            note_path = write_note(doc)
            item = {
                "title": doc.title,
                "url": doc.url,
                "source_name": doc.source_name,
                "source_type": doc.source_type,
                "published_date": doc.published_date,
                "tags": doc.tags,
                "note_file": str(note_path.relative_to(OUTPUT_DIR)),
            }
            manifest.append(item)
            source_items.append(item)
            print(f"Saved: {doc.title}")
        write_source_index(source["name"], source_items)
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Done. Total documents: {len(manifest)}")


if __name__ == "__main__":
    main()

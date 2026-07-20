from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse, urlunparse
import hashlib
import json
import re
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"
CONTEXT_DIR = OUTPUT_DIR / "context"
DB_FILE = CONTEXT_DIR / "context.sqlite"
CHUNKS_FILE = CONTEXT_DIR / "chunks.jsonl"
GRAPH_FILE = CONTEXT_DIR / "graph.json"
INDEX_FILE = CONTEXT_DIR / "CONTEXT_INDEX.md"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def digest(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def canonical_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = "https" if parsed.scheme in {"http", "https"} else parsed.scheme
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, parsed.netloc.lower(), path, "", "", ""))


def extracted_content(note_text: str) -> str:
    marker = "## Extracted Content"
    notes_marker = "## My Architecture Notes"
    if marker not in note_text:
        return note_text.strip()
    content = note_text.split(marker, 1)[1]
    if notes_marker in content:
        content = content.split(notes_marker, 1)[0]
    return content.strip("\n -")


def markdown_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    heading = "Overview"
    body: list[str] = []
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            current = "\n".join(body).strip()
            if current:
                sections.append((heading, current))
            heading = match.group(2).strip()
            body = []
        else:
            body.append(line)
    current = "\n".join(body).strip()
    if current:
        sections.append((heading, current))
    return sections or [("Overview", text.strip())]


def split_large_text(text: str, max_chars: int, overlap_chars: int) -> Iterable[str]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                yield current.strip()
                current = ""
            start = 0
            while start < len(paragraph):
                end = min(start + max_chars, len(paragraph))
                yield paragraph[start:end].strip()
                if end == len(paragraph):
                    break
                start = max(end - overlap_chars, start + 1)
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            yield current.strip()
            overlap = current[-overlap_chars:].strip() if overlap_chars else ""
            next_value = f"{overlap}\n\n{paragraph}".strip() if overlap else paragraph
            current = next_value if len(next_value) <= max_chars else paragraph
        else:
            current = paragraph

    if current:
        yield current.strip()


def build_chunks(document: dict, note_text: str, max_chars: int, overlap_chars: int) -> list[dict]:
    chunks: list[dict] = []
    content = extracted_content(note_text)
    ordinal = 0
    for heading, section_text in markdown_sections(content):
        for text in split_large_text(section_text, max_chars, overlap_chars):
            ordinal += 1
            seed = f"{document['document_id']}:{ordinal}:{text}"
            chunk_id = f"chunk-{digest(seed)}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": document["document_id"],
                    "ordinal": ordinal,
                    "title": document["title"],
                    "heading": heading,
                    "text": text,
                    "token_estimate": max(1, len(text) // 4),
                    "url": document["url"],
                    "source_name": document["source_name"],
                    "source_type": document["source_type"],
                    "published_date": document.get("published_date"),
                    "tags": document.get("tags", []),
                    "metadata": document.get("metadata", {}),
                }
            )
    return chunks


def create_schema(connection: sqlite3.Connection) -> bool:
    connection.executescript(
        """
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;

        DROP TABLE IF EXISTS chunks_fts;
        DROP TABLE IF EXISTS metadata;
        DROP TABLE IF EXISTS relationships;
        DROP TABLE IF EXISTS tags;
        DROP TABLE IF EXISTS chunks;
        DROP TABLE IF EXISTS documents;

        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE documents (
            document_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            source_name TEXT NOT NULL,
            source_type TEXT NOT NULL,
            author TEXT,
            published_date TEXT,
            collected_at TEXT,
            content_hash TEXT,
            note_file TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        );

        CREATE TABLE chunks (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
            ordinal INTEGER NOT NULL,
            heading TEXT NOT NULL,
            text TEXT NOT NULL,
            token_estimate INTEGER NOT NULL,
            UNIQUE(document_id, ordinal)
        );

        CREATE TABLE tags (
            document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
            tag TEXT NOT NULL,
            PRIMARY KEY(document_id, tag)
        );

        CREATE TABLE relationships (
            source_id TEXT NOT NULL,
            relationship TEXT NOT NULL,
            target_id TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            PRIMARY KEY(source_id, relationship, target_id)
        );

        CREATE INDEX idx_chunks_document ON chunks(document_id, ordinal);
        CREATE INDEX idx_tags_tag ON tags(tag, document_id);
        CREATE INDEX idx_relationships_target ON relationships(target_id, relationship);
        """
    )
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE chunks_fts USING fts5("
            "chunk_id UNINDEXED, document_id UNINDEXED, title, heading, text, tags, "
            "tokenize='porter unicode61')"
        )
        return True
    except sqlite3.OperationalError:
        connection.execute(
            "CREATE TABLE chunks_fts ("
            "chunk_id TEXT PRIMARY KEY, document_id TEXT, title TEXT, heading TEXT, text TEXT, tags TEXT)"
        )
        return False


def populate_database(connection: sqlite3.Connection, documents: list[dict], chunks: list[dict]) -> bool:
    fts_enabled = create_schema(connection)
    url_to_document = {canonical_url(document["url"]): document["document_id"] for document in documents}

    for document in documents:
        connection.execute(
            """
            INSERT INTO documents (
                document_id, title, url, source_name, source_type, author,
                published_date, collected_at, content_hash, note_file, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document["document_id"],
                document["title"],
                document["url"],
                document["source_name"],
                document["source_type"],
                document.get("author"),
                document.get("published_date"),
                document.get("collected_at"),
                document.get("content_hash"),
                document["note_file"],
                json.dumps(document.get("metadata", {}), ensure_ascii=False, sort_keys=True),
            ),
        )
        source_id = f"source:{document['source_name']}"
        connection.execute(
            "INSERT OR IGNORE INTO relationships(source_id, relationship, target_id) VALUES (?, 'FROM_SOURCE', ?)",
            (document["document_id"], source_id),
        )
        section = document.get("metadata", {}).get("catalog_section")
        if section:
            connection.execute(
                "INSERT OR IGNORE INTO relationships(source_id, relationship, target_id) VALUES (?, 'IN_SECTION', ?)",
                (document["document_id"], f"section:{section}"),
            )
        for tag in sorted(set(document.get("tags", []))):
            connection.execute("INSERT INTO tags(document_id, tag) VALUES (?, ?)", (document["document_id"], tag))
            connection.execute(
                "INSERT OR IGNORE INTO relationships(source_id, relationship, target_id) VALUES (?, 'TAGGED_WITH', ?)",
                (document["document_id"], f"tag:{tag}"),
            )
        for link in document.get("links", []):
            target_id = url_to_document.get(canonical_url(link))
            if target_id and target_id != document["document_id"]:
                connection.execute(
                    "INSERT OR IGNORE INTO relationships(source_id, relationship, target_id) VALUES (?, 'REFERENCES', ?)",
                    (document["document_id"], target_id),
                )

    for chunk in chunks:
        connection.execute(
            "INSERT INTO chunks(chunk_id, document_id, ordinal, heading, text, token_estimate) VALUES (?, ?, ?, ?, ?, ?)",
            (
                chunk["chunk_id"],
                chunk["document_id"],
                chunk["ordinal"],
                chunk["heading"],
                chunk["text"],
                chunk["token_estimate"],
            ),
        )
        connection.execute(
            "INSERT INTO chunks_fts(chunk_id, document_id, title, heading, text, tags) VALUES (?, ?, ?, ?, ?, ?)",
            (
                chunk["chunk_id"],
                chunk["document_id"],
                chunk["title"],
                chunk["heading"],
                chunk["text"],
                " ".join(chunk.get("tags", [])),
            ),
        )

    connection.execute("INSERT INTO metadata(key, value) VALUES ('fts5_available', ?)", (str(fts_enabled).lower(),))
    connection.execute("INSERT INTO metadata(key, value) VALUES ('schema_version', '1')")
    connection.commit()
    return fts_enabled


def build_graph(documents: list[dict]) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []
    url_to_document = {canonical_url(document["url"]): document["document_id"] for document in documents}

    for document in documents:
        document_id = document["document_id"]
        nodes[document_id] = {
            "id": document_id,
            "type": "document",
            "label": document["title"],
            "url": document["url"],
            "source": document["source_name"],
        }
        source_id = f"source:{document['source_name']}"
        nodes[source_id] = {"id": source_id, "type": "source", "label": document["source_name"]}
        edges.append({"source": document_id, "type": "FROM_SOURCE", "target": source_id})

        section = document.get("metadata", {}).get("catalog_section")
        if section:
            section_id = f"section:{section}"
            nodes[section_id] = {"id": section_id, "type": "section", "label": section}
            edges.append({"source": document_id, "type": "IN_SECTION", "target": section_id})

        for tag in sorted(set(document.get("tags", []))):
            tag_id = f"tag:{tag}"
            nodes[tag_id] = {"id": tag_id, "type": "tag", "label": tag}
            edges.append({"source": document_id, "type": "TAGGED_WITH", "target": tag_id})

        for link in document.get("links", []):
            target_id = url_to_document.get(canonical_url(link))
            if target_id and target_id != document_id:
                edges.append({"source": document_id, "type": "REFERENCES", "target": target_id})

    unique_edges = {(edge["source"], edge["type"], edge["target"]): edge for edge in edges}
    return {"nodes": list(nodes.values()), "edges": list(unique_edges.values())}


def write_context_index(documents: list[dict], chunks: list[dict], fts_enabled: bool) -> None:
    source_counts = Counter(document["source_name"] for document in documents)
    section_counts = Counter(
        document.get("metadata", {}).get("catalog_section", "Uncategorized") for document in documents
    )
    tag_counts = Counter(tag for document in documents for tag in document.get("tags", []))

    lines = [
        "# Engineering Knowledge Context Index",
        "",
        f"- Documents: {len(documents)}",
        f"- Chunks: {len(chunks)}",
        f"- SQLite FTS5: {'enabled' if fts_enabled else 'unavailable; LIKE fallback required'}",
        "",
        "## Sources",
        "",
    ]
    lines.extend(f"- {name}: {count}" for name, count in source_counts.most_common())
    lines.extend(["", "## Catalog Sections", ""])
    lines.extend(f"- {name}: {count}" for name, count in section_counts.most_common())
    lines.extend(["", "## Top Tags", ""])
    lines.extend(f"- {name}: {count}" for name, count in tag_counts.most_common(50))
    INDEX_FILE.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = ArgumentParser(description="Build a local retrieval context layer from collected architecture notes.")
    parser.add_argument("--chunk-size", type=int, default=1800, help="Maximum characters per chunk.")
    parser.add_argument("--overlap", type=int, default=180, help="Character overlap between adjacent chunks.")
    args = parser.parse_args()

    if not MANIFEST_FILE.exists():
        raise FileNotFoundError(f"Run scripts/collect.py first; missing {MANIFEST_FILE}")
    if args.chunk_size < 400:
        raise ValueError("--chunk-size must be at least 400 characters")
    if args.overlap < 0 or args.overlap >= args.chunk_size:
        raise ValueError("--overlap must be non-negative and smaller than --chunk-size")

    documents = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    chunks: list[dict] = []
    valid_documents: list[dict] = []
    for document in documents:
        note_path = OUTPUT_DIR / document["note_file"]
        if not note_path.exists():
            print(f"Skipping missing note: {note_path}")
            continue
        document_chunks = build_chunks(
            document,
            note_path.read_text(encoding="utf-8", errors="ignore"),
            args.chunk_size,
            args.overlap,
        )
        if not document_chunks:
            continue
        valid_documents.append(document)
        chunks.extend(document_chunks)

    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    with CHUNKS_FILE.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    if DB_FILE.exists():
        DB_FILE.unlink()
    with sqlite3.connect(DB_FILE) as connection:
        fts_enabled = populate_database(connection, valid_documents, chunks)

    GRAPH_FILE.write_text(json.dumps(build_graph(valid_documents), indent=2, ensure_ascii=False), encoding="utf-8")
    write_context_index(valid_documents, chunks, fts_enabled)
    print(f"Built context layer: {len(valid_documents)} documents, {len(chunks)} chunks")
    print(f"Database: {DB_FILE}")


if __name__ == "__main__":
    main()

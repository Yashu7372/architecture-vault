from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Any
from urllib.parse import urlparse, urlunparse
import hashlib
import json
import re
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from processing.context_semantics import (
    build_concept_links,
    concept_summary,
    enrich_documents_and_chunks,
)
from processing.knowledge_enrichment import (
    build_multilens_learning_units,
    concept_relation_statistics,
    load_yaml,
    serializable_source_quality,
)
from settings import OUTPUT_DIR

MANIFEST_FILE = OUTPUT_DIR / "manifest.json"
CONTEXT_DIR = OUTPUT_DIR / "context"
DB_FILE = CONTEXT_DIR / "context.sqlite"
CHUNKS_FILE = CONTEXT_DIR / "chunks.jsonl"
GRAPH_FILE = CONTEXT_DIR / "graph.json"
INDEX_FILE = CONTEXT_DIR / "CONTEXT_INDEX.md"
CONCEPTS_FILE = CONTEXT_DIR / "concepts.json"
RELATIONS_FILE = CONTEXT_DIR / "relations.json"
DUPLICATES_FILE = CONTEXT_DIR / "duplicates.json"
LEARNING_UNITS_FILE = CONTEXT_DIR / "learning-units.json"
LATEST_DELTA_FILE = OUTPUT_DIR / "deltas" / "latest.json"
TAXONOMY_FILE = ROOT / "config" / "knowledge-taxonomy.yaml"
EVIDENCE_POLICY_FILE = ROOT / "config" / "evidence-policy.yaml"
LEARNING_LENSES_FILE = ROOT / "config" / "learning-lenses.yaml"

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+.#/_-]*")
TRUST_NOTICE_PREFIX = "> TRUST NOTICE:"


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
    lines = [line for line in content.splitlines() if not line.strip().startswith(TRUST_NOTICE_PREFIX)]
    return "\n".join(lines).strip("\n -")


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


def is_meaningful_text(text: str) -> bool:
    """Reject boilerplate/empty fragments before they enter retrieval context."""
    value = text.strip()
    if not value:
        return False
    without_fences = re.sub(r"```[A-Za-z0-9_-]*", " ", value)
    words = WORD_RE.findall(without_fences)
    alnum = sum(1 for char in without_fences if char.isalnum())
    if len(words) >= 8 and alnum >= 40:
        return True
    # Code/config blocks often have fewer natural-language words but enough
    # information density to remain useful evidence.
    return len(value) >= 180 and alnum >= 90


def build_chunks(document: dict, note_text: str, max_chars: int, overlap_chars: int) -> list[dict]:
    chunks: list[dict] = []
    content = extracted_content(note_text)
    ordinal = 0
    for heading, section_text in markdown_sections(content):
        for text in split_large_text(section_text, max_chars, overlap_chars):
            if not is_meaningful_text(text):
                continue
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
                    "capability_id": document.get("capability_id") or (document.get("metadata", {}) or {}).get("capability_id"),
                    "trust_boundary": document.get("trust_boundary") or (document.get("metadata", {}) or {}).get("trust_boundary", "UNTRUSTED_EXTERNAL"),
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
        DROP TABLE IF EXISTS knowledge_deltas;
        DROP TABLE IF EXISTS learning_units;
        DROP TABLE IF EXISTS inferred_relations;
        DROP TABLE IF EXISTS chunk_concepts;
        DROP TABLE IF EXISTS concepts;
        DROP TABLE IF EXISTS duplicate_evidence;
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
            capability_id TEXT,
            trust_boundary TEXT NOT NULL DEFAULT 'UNTRUSTED_EXTERNAL',
            author TEXT,
            published_date TEXT,
            collected_at TEXT,
            content_hash TEXT,
            raw_content_hash TEXT,
            note_file TEXT NOT NULL,
            source_tier TEXT,
            source_quality_score REAL,
            authority_type TEXT,
            duplicate_group_id TEXT,
            evidence_unit_id TEXT,
            metadata_json TEXT NOT NULL
        );

        CREATE TABLE chunks (
            chunk_id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
            ordinal INTEGER NOT NULL,
            heading TEXT NOT NULL,
            text TEXT NOT NULL,
            gist TEXT NOT NULL DEFAULT '',
            token_estimate INTEGER NOT NULL,
            page_number INTEGER,
            evidence_unit_id TEXT,
            source_tier TEXT,
            source_quality_score REAL,
            authority_type TEXT,
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

        CREATE TABLE duplicate_evidence (
            duplicate_group_id TEXT NOT NULL,
            document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
            representative_document_id TEXT NOT NULL,
            duplicate_type TEXT NOT NULL,
            similarity REAL NOT NULL,
            PRIMARY KEY(duplicate_group_id, document_id)
        );

        CREATE TABLE concepts (
            concept_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            domain TEXT,
            aliases_json TEXT NOT NULL DEFAULT '[]',
            keywords_json TEXT NOT NULL DEFAULT '[]',
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE chunk_concepts (
            chunk_id TEXT NOT NULL REFERENCES chunks(chunk_id) ON DELETE CASCADE,
            concept_id TEXT NOT NULL REFERENCES concepts(concept_id) ON DELETE CASCADE,
            score REAL NOT NULL,
            evidence_state TEXT NOT NULL,
            matched_terms_json TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY(chunk_id, concept_id)
        );

        CREATE TABLE inferred_relations (
            relation_id TEXT PRIMARY KEY,
            subject_concept_id TEXT NOT NULL REFERENCES concepts(concept_id),
            predicate TEXT NOT NULL,
            object_concept_id TEXT NOT NULL REFERENCES concepts(concept_id),
            confidence REAL NOT NULL,
            evidence_state TEXT NOT NULL,
            evidence_json TEXT NOT NULL,
            statistics_json TEXT NOT NULL
        );

        CREATE TABLE learning_units (
            learning_unit_id TEXT PRIMARY KEY,
            concept_id TEXT NOT NULL REFERENCES concepts(concept_id),
            lens TEXT NOT NULL,
            depth_level TEXT NOT NULL,
            reading_minutes INTEGER NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            content_json TEXT NOT NULL,
            evidence_json TEXT NOT NULL
        );

        CREATE TABLE knowledge_deltas (
            delta_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            change_type TEXT NOT NULL,
            document_id TEXT,
            source_name TEXT,
            priority TEXT,
            priority_score REAL,
            required_action TEXT,
            payload_json TEXT NOT NULL
        );

        CREATE INDEX idx_chunks_document ON chunks(document_id, ordinal);
        CREATE INDEX idx_chunks_evidence_unit ON chunks(evidence_unit_id);
        CREATE INDEX idx_tags_tag ON tags(tag, document_id);
        CREATE INDEX idx_relationships_target ON relationships(target_id, relationship);
        CREATE INDEX idx_chunk_concepts_concept ON chunk_concepts(concept_id, score DESC);
        CREATE INDEX idx_relations_subject ON inferred_relations(subject_concept_id, confidence DESC);
        CREATE INDEX idx_relations_object ON inferred_relations(object_concept_id, confidence DESC);
        CREATE INDEX idx_learning_units_concept ON learning_units(concept_id, lens);
        CREATE INDEX idx_delta_document ON knowledge_deltas(document_id, priority_score DESC);
        """
    )
    try:
        connection.execute(
            "CREATE VIRTUAL TABLE chunks_fts USING fts5("
            "chunk_id UNINDEXED, document_id UNINDEXED, title, heading, text, gist, tags, "
            "tokenize='porter unicode61')"
        )
        return True
    except sqlite3.OperationalError:
        connection.execute(
            "CREATE TABLE chunks_fts ("
            "chunk_id TEXT PRIMARY KEY, document_id TEXT, title TEXT, heading TEXT, text TEXT, gist TEXT, tags TEXT)"
        )
        return False


def populate_database(
    connection: sqlite3.Connection,
    documents: list[dict],
    chunks: list[dict],
    *,
    taxonomy: dict[str, Any] | None = None,
    concept_links: list[dict[str, Any]] | None = None,
    relations: list[dict[str, Any]] | None = None,
    duplicates: list[Any] | None = None,
    learning_units: list[dict[str, Any]] | None = None,
    source_scores: dict[str, Any] | None = None,
    evidence_unit_by_document: dict[str, str] | None = None,
    latest_delta: dict[str, Any] | None = None,
) -> bool:
    taxonomy = taxonomy or {"concepts": []}
    concept_links = concept_links or []
    relations = relations or []
    duplicates = duplicates or []
    learning_units = learning_units or []
    source_scores = source_scores or {}
    evidence_unit_by_document = evidence_unit_by_document or {}

    fts_enabled = create_schema(connection)
    url_to_document = {canonical_url(document["url"]): document["document_id"] for document in documents}
    duplicate_group_by_document = {candidate.document_id: candidate.duplicate_group_id for candidate in duplicates}

    for document in documents:
        quality = source_scores.get(document["document_id"])
        metadata = document.get("metadata", {}) or {}
        capability_id = document.get("capability_id") or metadata.get("capability_id")
        trust_boundary = document.get("trust_boundary") or metadata.get("trust_boundary", "UNTRUSTED_EXTERNAL")
        connection.execute(
            """
            INSERT INTO documents (
                document_id, title, url, source_name, source_type, capability_id,
                trust_boundary, author, published_date, collected_at, content_hash,
                raw_content_hash, note_file, source_tier, source_quality_score,
                authority_type, duplicate_group_id, evidence_unit_id, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document["document_id"],
                document["title"],
                document["url"],
                document["source_name"],
                document["source_type"],
                capability_id,
                trust_boundary,
                document.get("author"),
                document.get("published_date"),
                document.get("collected_at"),
                document.get("content_hash"),
                document.get("raw_content_hash") or metadata.get("raw_content_sha256"),
                document["note_file"],
                quality.tier if quality else None,
                quality.score if quality else None,
                quality.authority if quality else None,
                duplicate_group_by_document.get(document["document_id"]),
                evidence_unit_by_document.get(document["document_id"], document["document_id"]),
                json.dumps(metadata, ensure_ascii=False, sort_keys=True),
            ),
        )
        source_id = f"source:{document['source_name']}"
        connection.execute(
            "INSERT OR IGNORE INTO relationships(source_id, relationship, target_id) VALUES (?, 'FROM_SOURCE', ?)",
            (document["document_id"], source_id),
        )
        if capability_id:
            connection.execute(
                "INSERT OR IGNORE INTO relationships(source_id, relationship, target_id) VALUES (?, 'COLLECTED_BY', ?)",
                (document["document_id"], f"capability:{capability_id}"),
            )
        section = metadata.get("catalog_section")
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

    for candidate in duplicates:
        connection.execute(
            """
            INSERT INTO duplicate_evidence(
                duplicate_group_id, document_id, representative_document_id, duplicate_type, similarity
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                candidate.duplicate_group_id,
                candidate.document_id,
                candidate.representative_document_id,
                candidate.duplicate_type,
                candidate.similarity,
            ),
        )

    for concept in taxonomy.get("concepts", []) or []:
        connection.execute(
            """
            INSERT INTO concepts(concept_id, name, domain, aliases_json, keywords_json, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                concept["id"],
                concept.get("name", concept["id"]),
                concept.get("domain"),
                json.dumps(concept.get("aliases", []), ensure_ascii=False),
                json.dumps(concept.get("keywords", []), ensure_ascii=False),
                json.dumps(
                    {key: value for key, value in concept.items() if key not in {"id", "name", "domain", "aliases", "keywords"}},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            ),
        )

    for chunk in chunks:
        connection.execute(
            """
            INSERT INTO chunks(
                chunk_id, document_id, ordinal, heading, text, gist, token_estimate,
                page_number, evidence_unit_id, source_tier, source_quality_score, authority_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk["chunk_id"],
                chunk["document_id"],
                chunk["ordinal"],
                chunk["heading"],
                chunk["text"],
                chunk.get("gist", ""),
                chunk["token_estimate"],
                chunk.get("page_number"),
                chunk.get("evidence_unit_id"),
                chunk.get("source_tier"),
                chunk.get("source_quality_score"),
                chunk.get("authority_type"),
            ),
        )
        connection.execute(
            "INSERT INTO chunks_fts(chunk_id, document_id, title, heading, text, gist, tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                chunk["chunk_id"],
                chunk["document_id"],
                chunk["title"],
                chunk["heading"],
                chunk["text"],
                chunk.get("gist", ""),
                " ".join(chunk.get("tags", [])),
            ),
        )

    for link in concept_links:
        connection.execute(
            """
            INSERT INTO chunk_concepts(chunk_id, concept_id, score, evidence_state, matched_terms_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                link["chunk_id"],
                link["concept_id"],
                link["score"],
                link.get("evidence_state", "EXTRACTED"),
                json.dumps(link.get("matched_terms", []), ensure_ascii=False),
            ),
        )

    for relation in relations:
        connection.execute(
            """
            INSERT INTO inferred_relations(
                relation_id, subject_concept_id, predicate, object_concept_id,
                confidence, evidence_state, evidence_json, statistics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relation["relation_id"],
                relation["subject_concept_id"],
                relation["predicate"],
                relation["object_concept_id"],
                relation["confidence"],
                relation.get("evidence_state", "INFERRED"),
                json.dumps(
                    {
                        "chunk_ids": relation.get("chunk_ids", []),
                        "document_ids": relation.get("document_ids", []),
                    },
                    ensure_ascii=False,
                ),
                json.dumps(relation.get("statistics", {}), ensure_ascii=False, sort_keys=True),
            ),
        )

    for unit in learning_units:
        connection.execute(
            """
            INSERT INTO learning_units(
                learning_unit_id, concept_id, lens, depth_level, reading_minutes,
                title, status, content_json, evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                unit["learning_unit_id"],
                unit["concept_id"],
                unit["lens"],
                unit["depth_level"],
                unit["reading_minutes"],
                unit["title"],
                unit["status"],
                json.dumps(unit.get("content", {}), ensure_ascii=False),
                json.dumps(unit.get("evidence", []), ensure_ascii=False),
            ),
        )

    if latest_delta:
        run_id = str(latest_delta.get("run_id", "unknown"))
        for delta in latest_delta.get("changes", []) or []:
            connection.execute(
                """
                INSERT OR REPLACE INTO knowledge_deltas(
                    delta_id, run_id, change_type, document_id, source_name,
                    priority, priority_score, required_action, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    delta["delta_id"],
                    run_id,
                    delta.get("change_type"),
                    delta.get("document_id"),
                    delta.get("source_name"),
                    delta.get("priority"),
                    delta.get("priority_score"),
                    delta.get("required_action"),
                    json.dumps(delta, ensure_ascii=False, sort_keys=True),
                ),
            )

    metadata_values = {
        "fts5_available": str(fts_enabled).lower(),
        "schema_version": "3",
        "semantic_authority": "candidate-evidence-backed",
        "promotion_allowed": "false",
        "raw_external_content_role": "data-not-instructions",
    }
    for key, value in metadata_values.items():
        connection.execute("INSERT INTO metadata(key, value) VALUES (?, ?)", (key, value))
    connection.commit()
    return fts_enabled


def build_graph(
    documents: list[dict],
    concept_links: list[dict[str, Any]] | None = None,
    relations: list[dict[str, Any]] | None = None,
) -> dict:
    concept_links = concept_links or []
    relations = relations or []
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
            "trust_boundary": document.get("trust_boundary") or (document.get("metadata", {}) or {}).get("trust_boundary"),
        }
        source_id = f"source:{document['source_name']}"
        nodes[source_id] = {"id": source_id, "type": "source", "label": document["source_name"]}
        edges.append({"source": document_id, "type": "FROM_SOURCE", "target": source_id})

        capability_id = document.get("capability_id") or (document.get("metadata", {}) or {}).get("capability_id")
        if capability_id:
            capability_node = f"capability:{capability_id}"
            nodes[capability_node] = {"id": capability_node, "type": "capability", "label": capability_id}
            edges.append({"source": document_id, "type": "COLLECTED_BY", "target": capability_node})

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

    concept_document_scores: dict[tuple[str, str], float] = {}
    for link in concept_links:
        key = (link["document_id"], link["concept_id"])
        concept_document_scores[key] = max(concept_document_scores.get(key, 0.0), float(link["score"]))
    for (document_id, concept_id), score in concept_document_scores.items():
        concept_node = f"concept:{concept_id}"
        nodes[concept_node] = {"id": concept_node, "type": "concept", "label": concept_id}
        edges.append(
            {
                "source": document_id,
                "type": "EVIDENCES_CONCEPT",
                "target": concept_node,
                "score": round(score, 4),
                "evidence_state": "EXTRACTED",
            }
        )

    for relation in relations:
        left = f"concept:{relation['subject_concept_id']}"
        right = f"concept:{relation['object_concept_id']}"
        nodes.setdefault(left, {"id": left, "type": "concept", "label": relation["subject_concept_id"]})
        nodes.setdefault(right, {"id": right, "type": "concept", "label": relation["object_concept_id"]})
        edges.append(
            {
                "source": left,
                "type": relation["predicate"],
                "target": right,
                "confidence": relation["confidence"],
                "evidence_state": relation.get("evidence_state", "INFERRED"),
            }
        )

    unique_edges = {
        (edge["source"], edge["type"], edge["target"]): edge
        for edge in edges
    }
    return {"nodes": list(nodes.values()), "edges": list(unique_edges.values())}


def write_context_index(
    documents: list[dict],
    chunks: list[dict],
    fts_enabled: bool,
    *,
    concepts: list[dict[str, Any]] | None = None,
    relations: list[dict[str, Any]] | None = None,
    duplicates: list[Any] | None = None,
    learning_units: list[dict[str, Any]] | None = None,
) -> None:
    concepts = concepts or []
    relations = relations or []
    duplicates = duplicates or []
    learning_units = learning_units or []
    source_counts = Counter(document["source_name"] for document in documents)
    section_counts = Counter(
        document.get("metadata", {}).get("catalog_section", "Uncategorized") for document in documents
    )
    tag_counts = Counter(tag for document in documents for tag in document.get("tags", []))
    tier_counts = Counter(str(chunk.get("source_tier", "unknown")) for chunk in chunks)

    lines = [
        "# Engineering Knowledge Context Index",
        "",
        "Authority: candidate/evidence-backed retrieval context; not curated portfolio truth.",
        "",
        f"- Schema version: 3",
        f"- Documents: {len(documents)}",
        f"- Meaningful chunks: {len(chunks)}",
        f"- Extracted concepts: {len(concepts)}",
        f"- Inferred relation candidates: {len(relations)}",
        f"- Duplicate evidence records: {len(duplicates)}",
        f"- Candidate learning units: {len(learning_units)}",
        f"- SQLite FTS5: {'enabled' if fts_enabled else 'unavailable; LIKE fallback required'}",
        "",
        "## Sources",
        "",
    ]
    lines.extend(f"- {name}: {count}" for name, count in source_counts.most_common())
    lines.extend(["", "## Source Tiers", ""])
    lines.extend(f"- {name}: {count}" for name, count in sorted(tier_counts.items()))
    lines.extend(["", "## Catalog Sections", ""])
    lines.extend(f"- {name}: {count}" for name, count in section_counts.most_common())
    lines.extend(["", "## Top Tags", ""])
    lines.extend(f"- {name}: {count}" for name, count in tag_counts.most_common(50))
    if concepts:
        lines.extend(["", "## Top Extracted Concepts", ""])
        for concept in sorted(concepts, key=lambda item: (-item["evidence_units"], -item["max_score"], item["concept_id"]))[:50]:
            lines.append(
                f"- {concept['name']} (`{concept['concept_id']}`): "
                f"{concept['evidence_units']} evidence units / {concept['evidence_chunks']} chunks"
            )
    INDEX_FILE.write_text("\n".join(lines), encoding="utf-8")


def _load_latest_delta() -> dict[str, Any] | None:
    if not LATEST_DELTA_FILE.is_file():
        return None
    try:
        return json.loads(LATEST_DELTA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


def main() -> None:
    parser = ArgumentParser(
        description="Build the schema-v3 local evidence/retrieval Knowledge Spine context from Architecture Vault evidence."
    )
    parser.add_argument("--chunk-size", type=int, default=1800, help="Maximum characters per chunk.")
    parser.add_argument("--overlap", type=int, default=180, help="Character overlap between adjacent chunks.")
    args = parser.parse_args()

    if not MANIFEST_FILE.exists():
        raise FileNotFoundError(f"Run scripts/collect.py first; missing {MANIFEST_FILE}")
    if args.chunk_size < 400:
        raise ValueError("--chunk-size must be at least 400 characters")
    if args.overlap < 0 or args.overlap >= args.chunk_size:
        raise ValueError("--overlap must be non-negative and smaller than --chunk-size")

    taxonomy = load_yaml(TAXONOMY_FILE, {"concepts": []})
    evidence_policy = load_yaml(EVIDENCE_POLICY_FILE, {})
    learning_lenses = load_yaml(LEARNING_LENSES_FILE, {"lenses": {}})
    documents = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))

    chunks: list[dict] = []
    valid_documents: list[dict] = []
    rejected_documents: list[str] = []
    for document in documents:
        note_path = OUTPUT_DIR / document["note_file"]
        if not note_path.exists():
            print(f"Skipping missing note: {note_path}")
            rejected_documents.append(document.get("document_id", document.get("url", "unknown")))
            continue
        document_chunks = build_chunks(
            document,
            note_path.read_text(encoding="utf-8", errors="ignore"),
            args.chunk_size,
            args.overlap,
        )
        if not document_chunks:
            print(f"Skipping document with no meaningful chunks: {document.get('title', document.get('url'))}")
            rejected_documents.append(document.get("document_id", document.get("url", "unknown")))
            continue
        valid_documents.append(document)
        chunks.extend(document_chunks)

    source_scores, duplicates, evidence_unit_by_document = enrich_documents_and_chunks(
        valid_documents,
        chunks,
        evidence_policy=evidence_policy,
    )
    concept_links = build_concept_links(chunks, taxonomy)
    relations = concept_relation_statistics(concept_links, chunks)
    learning_units = build_multilens_learning_units(
        taxonomy,
        chunks,
        concept_links,
        source_scores,
        learning_lenses,
    )
    concepts = concept_summary(taxonomy, concept_links, chunks)
    latest_delta = _load_latest_delta()

    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    with CHUNKS_FILE.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    if DB_FILE.exists():
        DB_FILE.unlink()
    with sqlite3.connect(DB_FILE) as connection:
        fts_enabled = populate_database(
            connection,
            valid_documents,
            chunks,
            taxonomy=taxonomy,
            concept_links=concept_links,
            relations=relations,
            duplicates=duplicates,
            learning_units=learning_units,
            source_scores=source_scores,
            evidence_unit_by_document=evidence_unit_by_document,
            latest_delta=latest_delta,
        )

    GRAPH_FILE.write_text(
        json.dumps(build_graph(valid_documents, concept_links, relations), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    CONCEPTS_FILE.write_text(json.dumps(concepts, indent=2, ensure_ascii=False), encoding="utf-8")
    RELATIONS_FILE.write_text(json.dumps(relations, indent=2, ensure_ascii=False), encoding="utf-8")
    DUPLICATES_FILE.write_text(
        json.dumps([candidate.__dict__ for candidate in duplicates], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    LEARNING_UNITS_FILE.write_text(json.dumps(learning_units, indent=2, ensure_ascii=False), encoding="utf-8")
    write_context_index(
        valid_documents,
        chunks,
        fts_enabled,
        concepts=concepts,
        relations=relations,
        duplicates=duplicates,
        learning_units=learning_units,
    )

    quality_report = {
        "schema_version": 3,
        "documents_in_manifest": len(documents),
        "documents_indexed": len(valid_documents),
        "documents_rejected_no_meaningful_chunks": len(rejected_documents),
        "rejected_document_ids": rejected_documents,
        "chunks": len(chunks),
        "concept_links": len(concept_links),
        "concepts_with_evidence": len(concepts),
        "relation_candidates": len(relations),
        "duplicate_records": len(duplicates),
        "learning_units": len(learning_units),
        "source_quality": {
            document_id: serializable_source_quality(value) for document_id, value in source_scores.items()
        },
    }
    (CONTEXT_DIR / "quality-report.json").write_text(
        json.dumps(quality_report, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )

    print(f"Built context layer: {len(valid_documents)} documents, {len(chunks)} meaningful chunks")
    print(
        f"Semantic candidates: {len(concepts)} concepts, {len(relations)} relations, "
        f"{len(learning_units)} learning units"
    )
    print(f"Database: {DB_FILE}")


if __name__ == "__main__":
    main()

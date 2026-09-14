from pathlib import Path
import sqlite3
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_context import build_chunks, build_graph, populate_database


class ContextLayerTest(unittest.TestCase):
    def setUp(self):
        self.document = {
            "document_id": "doc-1",
            "title": "Reliable Event Processing",
            "url": "https://example.com/reliable-events",
            "source_name": "example-catalog",
            "source_type": "web",
            "author": "Example Author",
            "published_date": "2026-01-01",
            "collected_at": "2026-07-20T00:00:00+00:00",
            "content_hash": "abc",
            "note_file": "notes/example.md",
            "tags": ["event-driven", "reliability"],
            "links": [],
            "metadata": {"catalog_section": "System Design Fundamentals"},
        }
        self.note = """
# Reliable Event Processing

## Extracted Content

### Idempotency

Consumers should record processed event identifiers before applying side effects.

### Retry Handling

Retries need bounded backoff and a dead-letter path for poison messages.

## My Architecture Notes

### Problem Being Solved
"""

    def test_builds_chunks_database_and_graph(self):
        chunks = build_chunks(self.document, self.note, max_chars=500, overlap_chars=50)
        self.assertEqual(2, len(chunks))
        self.assertEqual("Idempotency", chunks[0]["heading"])

        with sqlite3.connect(":memory:") as connection:
            populate_database(connection, [self.document], chunks)
            document_count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            chunk_count = connection.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            tag_count = connection.execute("SELECT COUNT(*) FROM tags").fetchone()[0]

        self.assertEqual(1, document_count)
        self.assertEqual(2, chunk_count)
        self.assertEqual(2, tag_count)

        graph = build_graph([self.document])
        edge_types = {edge["type"] for edge in graph["edges"]}
        self.assertIn("FROM_SOURCE", edge_types)
        self.assertIn("IN_SECTION", edge_types)
        self.assertIn("TAGGED_WITH", edge_types)


if __name__ == "__main__":
    unittest.main()

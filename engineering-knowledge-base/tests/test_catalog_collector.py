from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collectors.base import KnowledgeDocument
from collectors.catalog_collector import CatalogCollector


class FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, markdown: str):
        self.markdown = markdown
        self.headers = {}

    def get(self, *_args, **_kwargs):
        return FakeResponse(self.markdown)


class FakeWebCollector:
    def extract_url(self, article_url: str, source: dict):
        return KnowledgeDocument(
            title=source["title"],
            url=article_url,
            source_name=source["name"],
            source_type="web",
            content="architecture context " * 40,
            tags=source.get("tags", []),
            metadata=source.get("document_metadata", {}),
        )


class CatalogCollectorTest(unittest.TestCase):
    MARKDOWN = """
## Case Studies
#### A companies
- [First Article](https://example.com/first/)
- [Chat Part 1](https://example.com/chat), [Chat Part 2](https://example.com/chat-part-2)

## Fundamentals
#### Messaging
- [First Article Again](http://example.com/first?ref=catalog)
- [Ignored](https://other.example.org/ignored)
"""

    def test_discovers_all_links_and_preserves_duplicate_locations(self):
        collector = CatalogCollector(FakeSession(self.MARKDOWN))
        entries = collector.discover_entries(
            {
                "name": "test-catalog",
                "type": "catalog",
                "url": "https://catalog.example/readme.md",
                "allow_domains": ["example.com"],
            }
        )

        self.assertEqual(3, len(entries))
        first = entries[0]
        self.assertEqual("https://example.com/first", first.url)
        self.assertEqual(
            (("Case Studies", "A companies"), ("Fundamentals", "Messaging")),
            first.locations,
        )
        self.assertEqual("https://example.com/chat-part-2", entries[2].url)

    def test_reports_resume_and_limit_counts(self):
        collector = CatalogCollector(FakeSession(self.MARKDOWN))
        collector.web_collector = FakeWebCollector()
        docs = collector.collect(
            {
                "name": "test-catalog",
                "type": "catalog",
                "url": "https://catalog.example/readme.md",
                "catalog_page": "https://catalog.example",
                "allow_domains": ["example.com"],
                "skip_urls": ["https://example.com/first"],
                "max_articles": 1,
                "min_content_chars": 100,
                "tags": ["system-design"],
            }
        )

        self.assertEqual(1, len(docs))
        self.assertEqual(3, collector.last_report["discovered"])
        self.assertEqual(1, collector.last_report["skipped_existing"])
        self.assertEqual(1, collector.last_report["attempted"])
        self.assertEqual(1, collector.last_report["deferred_by_limit"])
        self.assertEqual(1, collector.last_report["collected"])
        self.assertEqual(0, collector.last_report["failed"])


if __name__ == "__main__":
    unittest.main()

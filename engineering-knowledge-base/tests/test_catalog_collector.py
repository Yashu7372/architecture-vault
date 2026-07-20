from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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


class CatalogCollectorTest(unittest.TestCase):
    def test_discovers_all_links_and_preserves_duplicate_locations(self):
        markdown = """
## Case Studies
#### A companies
- [First Article](https://example.com/first/)
- [Chat Part 1](https://example.com/chat), [Chat Part 2](https://example.com/chat-part-2)

## Fundamentals
#### Messaging
- [First Article Again](http://example.com/first?ref=catalog)
- [Ignored](https://other.example.org/ignored)
"""
        collector = CatalogCollector(FakeSession(markdown))
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


if __name__ == "__main__":
    unittest.main()

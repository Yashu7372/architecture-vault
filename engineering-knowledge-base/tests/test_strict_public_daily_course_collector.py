from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collectors.strict_public_daily_course_collector import (
    StrictPublicDailyCourseCollector,
)
from collectors.substack_course_collector import ArticleSnapshot


class StrictPublicDailyCourseCollectorTest(unittest.TestCase):
    def setUp(self):
        self.collector = StrictPublicDailyCourseCollector()
        self.collector._active_source = {"reader_preview_max_chars": 7000}

    def test_anonymous_full_article_remains_public(self):
        body = "A complete public lesson. " * 80
        raw = f"""Title: Public lesson
Markdown Content:
{body}
"""

        snapshot = self.collector._article_from_reader_markdown(
            raw,
            "https://sdcourse.substack.com/p/day-8-public-example",
            min_public_chars=600,
            min_preview_chars=120,
        )

        self.assertEqual("public", snapshot.access_level)
        self.assertFalse(snapshot.explicit_paywall)
        self.assertIn("complete public lesson", snapshot.content)

    def test_paid_reader_response_is_reduced_to_visible_intro(self):
        intro = "This public introduction explains the problem and architecture. " * 15
        raw = f"""Title: Paid lesson
Markdown Content:
{intro}

Claim my free post

Subscriber implementation details that must not be retained.
"""

        snapshot = self.collector._article_from_reader_markdown(
            raw,
            "https://sdcourse.substack.com/p/day-10-paid-example",
            min_public_chars=600,
            min_preview_chars=120,
        )

        self.assertEqual("preview", snapshot.access_level)
        self.assertTrue(snapshot.explicit_paywall)
        self.assertIn("public introduction", snapshot.content)
        self.assertNotIn("Subscriber implementation", snapshot.content)
        self.assertNotIn("Claim my free post", snapshot.content)

    def test_explicit_paywall_snapshot_cannot_be_promoted_by_length(self):
        snapshot = ArticleSnapshot(
            title="Courtesy access lesson",
            content="Visible introduction. " * 100,
            published_date=None,
            links=tuple(),
            access_level="preview",
            explicit_paywall=True,
        )

        classified = self.collector._respect_article_access(
            snapshot,
            min_public_chars=600,
            min_preview_chars=120,
        )

        self.assertEqual("preview", classified.access_level)
        self.assertTrue(classified.explicit_paywall)


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collectors.substack_course_collector import SubstackCourseCollector


class FakeResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


class FakeSession:
    def __init__(self, pages: dict[str, str]):
        self.pages = pages
        self.headers = {}

    def get(self, url: str, **_kwargs):
        return FakeResponse(self.pages[url])


class SubstackCourseCollectorTest(unittest.TestCase):
    CURRICULUM_URL = "https://course.example.com/p/curriculum"
    SHARED_ARTICLE_URL = "https://course.example.com/p/shared-lesson"

    CURRICULUM_HTML = """
    <article>
      <h2>Module 1: Foundations</h2>
      <h3>Week 1: Setup</h3>
      <ol>
        <li>
          <a href="/p/shared-lesson">Day 1</a>
          <a href="/p/shared-lesson">: Build the local environment</a>
          <ul><li>Output: Reproducible workspace</li></ul>
        </li>
        <li>
          <a href="/p/shared-lesson">Day 2</a>
          <a href="/p/shared-lesson">: Add a configurable event generator</a>
          <ul><li>Output: Working generator</li></ul>
        </li>
      </ol>
    </article>
    """

    ARTICLE_HTML = """
    <html>
      <body>
        <h1>Shared lesson</h1>
        <time datetime="2026-01-01"></time>
        <article>
          <div class="available-content">
            <h2>Public explanation</h2>
            <p>{public_text}</p>
            <div class="paywall">
              <p>subscriber-only-secret</p>
            </div>
          </div>
        </article>
        <div>This post is for paid subscribers</div>
      </body>
    </html>
    """.format(public_text="public architecture explanation " * 20)

    def test_preserves_day_order_when_multiple_days_share_one_article(self):
        session = FakeSession(
            {
                self.CURRICULUM_URL: self.CURRICULUM_HTML,
                self.SHARED_ARTICLE_URL: self.ARTICLE_HTML,
            }
        )
        collector = SubstackCourseCollector(session)
        docs = collector.collect(
            {
                "name": "test-course",
                "type": "substack",
                "course_mode": True,
                "url": self.CURRICULUM_URL,
                "track": "python-js",
                "min_public_chars": 300,
                "min_preview_chars": 50,
                "tags": ["system-design"],
            }
        )

        self.assertEqual(2, len(docs))
        self.assertNotEqual(docs[0].url, docs[1].url)
        self.assertTrue(docs[0].url.endswith("#curriculum-day-001"))
        self.assertTrue(docs[1].url.endswith("#curriculum-day-002"))
        self.assertEqual(1, docs[0].metadata["curriculum_day"])
        self.assertEqual(2, docs[1].metadata["curriculum_day"])
        self.assertEqual("preview", docs[0].metadata["access_level"])
        self.assertNotIn("subscriber-only-secret", docs[0].content)
        self.assertIn("Original Stitched Study Guide", docs[0].content)
        self.assertEqual(2, collector.last_report["collected"])

    def test_resume_uses_unique_lesson_document_url(self):
        session = FakeSession(
            {
                self.CURRICULUM_URL: self.CURRICULUM_HTML,
                self.SHARED_ARTICLE_URL: self.ARTICLE_HTML,
            }
        )
        collector = SubstackCourseCollector(session)
        docs = collector.collect(
            {
                "name": "test-course",
                "type": "substack",
                "course_mode": True,
                "url": self.CURRICULUM_URL,
                "skip_urls": [f"{self.SHARED_ARTICLE_URL}#curriculum-day-001"],
                "max_articles": 1,
                "min_public_chars": 300,
                "min_preview_chars": 50,
            }
        )

        self.assertEqual(1, len(docs))
        self.assertEqual(2, docs[0].metadata["curriculum_day"])
        self.assertEqual(1, collector.last_report["skipped_existing"])


if __name__ == "__main__":
    unittest.main()

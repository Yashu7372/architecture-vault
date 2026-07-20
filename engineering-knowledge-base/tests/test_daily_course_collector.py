from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collectors.daily_course_collector import DailyCourseCollector


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


class DailyCourseCollectorTest(unittest.TestCase):
    def test_builds_two_part_learning_document_without_paywalled_text(self):
        curriculum_url = "https://course.example.com/p/curriculum"
        article_url = "https://course.example.com/p/day-one"
        curriculum = """
        <article>
          <h2>Module 1: Foundations</h2>
          <h3>Week 1: Setup</h3>
          <ol>
            <li>
              <a href="/p/day-one">Day 1: Build an idempotent event consumer</a>
              <ul><li>Output: Duplicate-safe consumer</li></ul>
            </li>
          </ol>
        </article>
        """
        article = """
        <html><body>
          <h1>Idempotency</h1>
          <article><div class="available-content">
            <p>Public architecture introduction with an event identifier and acknowledgement boundary.</p>
            <img src="https://images.example.com/architecture.png" alt="architecture" />
            <div class="paywall">subscriber-only-secret</div>
          </div></article>
          <div>This post is for paid subscribers</div>
        </body></html>
        """
        collector = DailyCourseCollector(FakeSession({curriculum_url: curriculum, article_url: article}))
        with patch.dict("os.environ", {}, clear=True):
            documents = collector.collect(
                {
                    "name": "test-daily-course",
                    "url": curriculum_url,
                    "track": "java-spring-boot",
                    "min_public_chars": 1000,
                    "min_preview_chars": 30,
                    "tags": ["system-design"],
                }
            )

        self.assertEqual(1, len(documents))
        document = documents[0]
        self.assertIn("## Part 1 — Public Source Capture", document.content)
        self.assertIn("architecture.png", document.content)
        self.assertIn("## Part 2 — Original Completed Lesson", document.content)
        self.assertNotIn("subscriber-only-secret", document.content)
        self.assertEqual("preview", document.metadata["access_level"])
        self.assertEqual("deterministic-template", document.metadata["lesson_completion_mode"])
        self.assertTrue(document.metadata["generated_original_lesson"])
        self.assertEqual("collected", collector.last_report["results"][0]["status"])


if __name__ == "__main__":
    unittest.main()

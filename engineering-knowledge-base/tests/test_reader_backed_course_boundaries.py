from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collectors.strict_public_daily_course_collector import (
    StrictPublicDailyCourseCollector,
)


class ReaderBackedCourseBoundaryTest(unittest.TestCase):
    def test_maps_roadmap_modules_and_week_resets_to_lesson_rows(self):
        markdown = """
* Module 1: Foundations of Log Processing (Days 1-30)
  * Week 1: Setting Up the Infrastructure
  * Week 2: Network-Based Log Collection
* Module 2: Scalable Log Processing (Days 31-60)
  * Week 3: Message Queues

1. [Day 1: Set up development environment](https://course.example/p/day-1-setup)
   * Output: Initialized repository
2. [Day 2: Build a generator](https://course.example/p/day-2-generator)
   * Output: Configurable event generator
7. [Day 7: Integrate local pipeline](https://course.example/p/day-7-integrate)
   * Output: Local pipeline

Integrate All Components (Day 8 to Day 14) into a Distributed Logging Platform

1. [Day 8: Build TCP server](https://course.example/p/day-8-tcp)
   * Output: TCP server
"""
        collector = StrictPublicDailyCourseCollector()
        base_lessons = collector._discover_lessons_from_markdown(
            markdown,
            {"url": "https://course.example/p/curriculum"},
        )
        lessons = collector._repair_curriculum_metadata(markdown, base_lessons)
        by_day = {lesson.day: lesson for lesson in lessons}

        self.assertEqual("Module 1: Foundations of Log Processing (Days 1-30)", by_day[1].module)
        self.assertEqual("Week 1: Setting Up the Infrastructure", by_day[1].week)
        self.assertEqual("Initialized repository", by_day[1].expected_output)
        self.assertEqual("Week 2: Network-Based Log Collection", by_day[8].week)
        self.assertEqual("Build TCP server", by_day[8].title)

    def test_later_day_reader_content_is_limited_to_public_intro(self):
        raw = """Title: Day 4
Published Time: 2026-01-01
Markdown Content:
Welcome to the lesson.

![Architecture](https://images.example/architecture.png)

The parser normalizes Apache, Nginx, and JSON records.

**Source code repository: https://github.com/example/private-course**

Implementation code that must not be retained.
"""
        collector = StrictPublicDailyCourseCollector()
        collector._active_source = {
            "verified_public_through_day": 3,
            "reader_preview_max_chars": 7000,
        }
        snapshot = collector._article_from_reader_markdown(
            raw,
            "https://course.example/p/day-4-log-parser",
            min_public_chars=100,
            min_preview_chars=20,
        )

        self.assertEqual("preview", snapshot.access_level)
        self.assertIn("Architecture", snapshot.content)
        self.assertIn("normalizes Apache", snapshot.content)
        self.assertNotIn("Source code repository", snapshot.content)
        self.assertNotIn("Implementation code", snapshot.content)

    def test_verified_free_day_overrides_signup_marker_after_public_body(self):
        raw = """Title: Day 2
Markdown Content:
A detailed public lesson explaining event generation, rate control, and validation.

Continue reading this post for free
"""
        collector = StrictPublicDailyCourseCollector()
        collector._active_source = {"verified_public_through_day": 3}
        snapshot = collector._article_from_reader_markdown(
            raw,
            "https://course.example/p/day-2-log-generator",
            min_public_chars=40,
            min_preview_chars=20,
        )

        self.assertEqual("public", snapshot.access_level)
        self.assertFalse(snapshot.explicit_paywall)
        self.assertIn("rate control", snapshot.content)
        self.assertNotIn("Continue reading", snapshot.content)


if __name__ == "__main__":
    unittest.main()

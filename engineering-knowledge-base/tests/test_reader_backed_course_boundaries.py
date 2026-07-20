from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collectors.reader_backed_substack_course_collector import (
    ReaderBackedSubstackCourseCollector,
)


class ReaderBackedCourseBoundaryTest(unittest.TestCase):
    def test_uses_detailed_curriculum_section_not_roadmap_state(self):
        markdown = """
# Course
#### The Definitive Roadmap
* Module 9: Advanced Performance and Optimization (Days 241-270)
  * Week 37: Storage Optimization

### 254-Lesson’s Distributed Log Processing System Implementation
## Module 1: Foundations of Log Processing (Days 1-30)
### Week 1: Setting Up the Infrastructure
1. [Day 1: Set up development environment](https://course.example/p/day-1-setup)
   * Output: Initialized repository
2. [Day 2: Build a generator](https://course.example/p/day-2-generator)
   * Output: Configurable event generator
"""
        collector = ReaderBackedSubstackCourseCollector()
        lessons = collector._discover_lessons_from_markdown(
            markdown,
            {"url": "https://course.example/p/curriculum"},
        )

        self.assertEqual(2, len(lessons))
        self.assertEqual("Module 1: Foundations of Log Processing (Days 1-30)", lessons[0].module)
        self.assertEqual("Week 1: Setting Up the Infrastructure", lessons[0].week)
        self.assertEqual("Initialized repository", lessons[0].expected_output)

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
        collector = ReaderBackedSubstackCourseCollector()
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

    def test_verified_free_day_can_keep_public_reader_content(self):
        raw = """Title: Day 2
Markdown Content:
A detailed public lesson explaining event generation, rate control, and validation.
"""
        collector = ReaderBackedSubstackCourseCollector()
        collector._active_source = {"verified_public_through_day": 3}
        snapshot = collector._article_from_reader_markdown(
            raw,
            "https://course.example/p/day-2-log-generator",
            min_public_chars=40,
            min_preview_chars=20,
        )

        self.assertEqual("public", snapshot.access_level)
        self.assertIn("rate control", snapshot.content)


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collectors.course_learning_builder import build_course_study_guide, infer_profile


class CourseLearningBuilderTest(unittest.TestCase):
    def test_selects_messaging_profile_for_queue_lesson(self):
        profile = infer_profile("Add consumer acknowledgements and dead letter queues")
        self.assertEqual("messaging-streaming", profile.key)

    def test_stitches_previous_and_next_lessons_into_original_guide(self):
        previous_lesson = SimpleNamespace(day=31, title="Set up RabbitMQ")
        lesson = SimpleNamespace(
            day=32,
            title="Create producers to send logs to message queues",
            expected_output="Log collector publishing to message queues",
            module="Module 2: Scalable Log Processing",
            week="Week 5: Message Queues for Log Processing",
        )
        next_lesson = SimpleNamespace(day=33, title="Implement consumers to process logs from queues")

        guide = build_course_study_guide(
            lesson=lesson,
            previous_lesson=previous_lesson,
            next_lesson=next_lesson,
            public_content="",
            access_level="curriculum-only",
        )

        self.assertIn("Day 31 — Set up RabbitMQ", guide)
        self.assertIn("Day 33 — Implement consumers", guide)
        self.assertIn("Log collector publishing to message queues", guide)
        self.assertIn("```mermaid", guide)
        self.assertIn("does not recreate", guide)


if __name__ == "__main__":
    unittest.main()

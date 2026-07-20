from __future__ import annotations

from pathlib import Path
from unittest.mock import patch
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collectors.course_completion_engine import build_completion_prompt, complete_course_lesson
from collectors.substack_course_collector import CourseLesson


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": "## Part 2 — Original Completed Lesson\n\nDetailed lesson"}}]}


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse()


class CourseCompletionEngineTest(unittest.TestCase):
    def setUp(self):
        self.lesson = CourseLesson(
            day=7,
            title="Idempotent Event Processing",
            expected_output="Duplicate-safe event consumer",
            module="Module 2",
            week="Week 1",
            article_url="https://sdcourse.substack.com/p/idempotency",
            curriculum_url="https://sdcourse.substack.com/p/curriculum",
            order=7,
        )

    def test_prompt_enforces_public_boundary_and_detailed_structure(self):
        prompt = build_completion_prompt(
            lesson=self.lesson,
            previous_lesson=None,
            next_lesson=None,
            public_content="A short public introduction.",
            access_level="preview",
            course_track="java-spring",
        )
        self.assertIn("Do not guess, reconstruct", prompt)
        self.assertIn("Part 2 — Original Completed Lesson", prompt)
        self.assertIn("Concurrency, Ordering, and Consistency", prompt)
        self.assertIn("Technology-Specific Notes for java-spring", prompt)

    def test_uses_deterministic_template_without_llm_configuration(self):
        with patch.dict("os.environ", {}, clear=True):
            result = complete_course_lesson(
                lesson=self.lesson,
                previous_lesson=None,
                next_lesson=None,
                public_content="",
                access_level="curriculum-only",
                course_track="python-js",
            )
        self.assertEqual("deterministic-template", result.mode)
        self.assertIn("Part 2 — Original Completed Lesson", result.content)
        self.assertIn("Failure Scenarios", result.content)

    def test_calls_openai_compatible_router_when_configured(self):
        session = FakeSession()
        environment = {
            "COURSE_LLM_BASE_URL": "https://router.example/v1",
            "COURSE_LLM_MODEL": "enterprise-model",
            "COURSE_LLM_API_KEY": "secret",
        }
        with patch.dict("os.environ", environment, clear=True):
            result = complete_course_lesson(
                lesson=self.lesson,
                previous_lesson=None,
                next_lesson=None,
                public_content="Public architecture overview",
                access_level="preview",
                course_track="java-spring",
                session=session,
            )
        self.assertEqual("llm", result.mode)
        self.assertEqual("enterprise-model", result.model)
        self.assertEqual("https://router.example/v1/chat/completions", session.calls[0][0])
        self.assertEqual("Bearer secret", session.calls[0][1]["headers"]["Authorization"])


if __name__ == "__main__":
    unittest.main()

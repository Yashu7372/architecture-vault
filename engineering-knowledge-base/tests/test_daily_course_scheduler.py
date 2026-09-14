from __future__ import annotations

from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SCRIPTS_DIR))

import run_daily_course_learning as scheduler


class DailyCourseSchedulerTest(unittest.TestCase):
    def test_splits_public_capture_from_original_completed_lesson(self):
        note = """# Day 1

## Extracted Content

## Part 1 — Public Source Capture

Public introduction and image.

---

## Part 2 — Original Completed Lesson

Detailed explanation.

---

## My Architecture Notes
"""
        public_capture, completed = scheduler.split_lesson_content(note)
        self.assertIn("Public Source Capture", public_capture)
        self.assertNotIn("Original Completed Lesson", public_capture)
        self.assertTrue(completed.startswith("## Part 2 — Original Completed Lesson"))
        self.assertIn("Detailed explanation", completed)

    def test_scheduler_state_finds_next_missing_day(self):
        items = [
            {"metadata": {"curriculum_day": 1}},
            {"metadata": {"curriculum_day": 2}},
            {"metadata": {"curriculum_day": 4}},
        ]
        state = {"tracks": {}}
        original_report = scheduler.report_for_source
        scheduler.report_for_source = lambda _source: {"discovered": 5}
        try:
            scheduler.update_scheduler_state(state, "course", items, [])
        finally:
            scheduler.report_for_source = original_report

        track = state["tracks"]["course"]
        self.assertEqual(3, track["completed_lessons"])
        self.assertEqual(3, track["next_pending_day"])
        self.assertEqual(2, track["remaining_lessons"])

    def test_json_state_write_is_atomic_and_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            scheduler.write_json(path, {"version": 1, "tracks": {}})
            self.assertEqual({"version": 1, "tracks": {}}, json.loads(path.read_text(encoding="utf-8")))
            self.assertFalse(path.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()

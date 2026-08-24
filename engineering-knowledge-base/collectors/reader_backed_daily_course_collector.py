from collectors.daily_course_collector import DailyCourseCollector
from collectors.reader_backed_substack_course_collector import (
    ReaderBackedSubstackCourseCollector,
)


class ReaderBackedDailyCourseCollector(
    DailyCourseCollector,
    ReaderBackedSubstackCourseCollector,
):
    """Daily lesson completion with a public Reader fallback for blocked pages."""

    pass

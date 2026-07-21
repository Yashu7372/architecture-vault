from __future__ import annotations

from collectors.strict_public_daily_course_collector import (
    StrictPublicDailyCourseCollector,
)


class PerPageAccessDailyCourseCollector(StrictPublicDailyCourseCollector):
    """Compatibility name for the strict per-page access collector.

    All classification is implemented by StrictPublicDailyCourseCollector so
    direct Substack HTML and anonymous reader responses follow one conservative
    rule. Keeping this class avoids breaking existing imports without adding a
    second, conflicting access path.
    """

    pass

from __future__ import annotations

import re

from collectors.reader_backed_substack_course_collector import (
    DETAILED_CURRICULUM_MARKERS,
)
from collectors.substack_course_collector import ArticleSnapshot
from collectors.anonymous_reader_daily_course_collector import (
    AnonymousReaderDailyCourseCollector,
)


class StrictPublicDailyCourseCollector(AnonymousReaderDailyCourseCollector):
    """Apply the publication's verified free-day and curriculum-section boundaries."""

    @staticmethod
    def _detailed_curriculum_section(markdown: str) -> str:
        lowered = markdown.lower()
        starts = []
        for marker in DETAILED_CURRICULUM_MARKERS:
            search_from = 0
            while True:
                index = lowered.find(marker, search_from)
                if index < 0:
                    break
                starts.append(index)
                search_from = index + len(marker)
        if starts:
            # The phrase also appears in title/intro metadata. The last occurrence
            # is the detailed Day 1..N curriculum section after the roadmap.
            return markdown[max(starts):]

        module_one_matches = list(
            re.finditer(r"(?mi)^#{1,4}\s+module\s+1\s*:", markdown)
        )
        if module_one_matches:
            return markdown[module_one_matches[-1].start():]
        return markdown

    def _article_from_reader_markdown(
        self,
        raw: str,
        article_url: str,
        *,
        min_public_chars: int,
        min_preview_chars: int,
    ) -> ArticleSnapshot:
        snapshot = super()._article_from_reader_markdown(
            raw,
            article_url,
            min_public_chars=min_public_chars,
            min_preview_chars=min_preview_chars,
        )
        day = self._day_from_article_url(article_url)
        verified_through = int(self._active_source.get("verified_public_through_day", 0))
        if (
            day is not None
            and day <= verified_through
            and len(snapshot.content) >= min_public_chars
        ):
            return ArticleSnapshot(
                title=snapshot.title,
                content=snapshot.content,
                published_date=snapshot.published_date,
                links=snapshot.links,
                access_level="public",
                explicit_paywall=False,
            )
        return snapshot

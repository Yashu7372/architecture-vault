from __future__ import annotations

import re

from collectors.reader_backed_substack_course_collector import (
    DETAILED_CURRICULUM_MARKERS,
)
from collectors.substack_course_collector import ArticleSnapshot, CourseLesson, DAY_RE, OUTPUT_RE
from collectors.anonymous_reader_daily_course_collector import (
    AnonymousReaderDailyCourseCollector,
)


class StrictPublicDailyCourseCollector(AnonymousReaderDailyCourseCollector):
    """Apply one public boundary regardless of direct or reader-backed transport."""

    def discover_lessons(self, source: dict):
        self._active_source = source
        try:
            markdown = self._reader_fetch(
                source["url"],
                RuntimeError("reader preferred for stable curriculum parsing"),
            )
            lessons = self._discover_lessons_from_markdown(markdown, source)
            if lessons:
                return self._repair_curriculum_metadata(markdown, lessons)
        except Exception:
            pass
        return super().discover_lessons(source)

    def _extract_public_article(
        self,
        article_url: str | None,
        *,
        min_public_chars: int,
        min_preview_chars: int,
    ) -> ArticleSnapshot:
        snapshot = super()._extract_public_article(
            article_url,
            min_public_chars=min_public_chars,
            min_preview_chars=min_preview_chars,
        )
        if not article_url:
            return snapshot

        day = self._day_from_article_url(article_url)
        verified_through = int(self._active_source.get("verified_public_through_day", 0))
        if day is not None and day <= verified_through:
            if len(snapshot.content) >= min_public_chars:
                return ArticleSnapshot(
                    title=snapshot.title,
                    content=snapshot.content,
                    published_date=snapshot.published_date,
                    links=snapshot.links,
                    access_level="public",
                    explicit_paywall=False,
                )
            return snapshot

        preview = self._introductory_preview(snapshot.content)
        if len(preview) < min_preview_chars:
            return ArticleSnapshot(
                title=snapshot.title,
                content="",
                published_date=snapshot.published_date,
                links=tuple(),
                access_level="curriculum-only",
                explicit_paywall=True,
            )
        return ArticleSnapshot(
            title=snapshot.title,
            content=preview,
            published_date=snapshot.published_date,
            links=snapshot.links,
            access_level="preview",
            explicit_paywall=True,
        )

    @staticmethod
    def _detailed_curriculum_section(markdown: str) -> str:
        module_one_matches = list(
            re.finditer(r"(?mi)^#{1,4}\s+module\s+1\s*:", markdown)
        )
        if module_one_matches:
            return markdown[module_one_matches[-1].start():]

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
            return markdown[max(starts):]
        return markdown

    def _repair_curriculum_metadata(
        self,
        markdown: str,
        lessons: list[CourseLesson],
    ) -> list[CourseLesson]:
        """Map roadmap modules/weeks to the sequential weekly Day groups."""
        module_ranges: list[tuple[int, int, str]] = []
        week_titles: list[str] = []
        day_section_started = False

        for raw_line in markdown.splitlines():
            plain = self._markdown_plain_text(raw_line.strip())
            if DAY_RE.search(plain):
                day_section_started = True
            if day_section_started:
                continue

            if plain.lower().startswith("module "):
                range_match = re.search(
                    r"days?\s+(\d+)\s*[-–—]\s*(\d+)",
                    plain,
                    re.IGNORECASE,
                )
                if range_match:
                    module_ranges.append(
                        (int(range_match.group(1)), int(range_match.group(2)), plain)
                    )
            elif plain.lower().startswith("week "):
                week_titles.append(plain)

        positioned: dict[int, dict] = {}
        pending_day: int | None = None
        week_index = -1
        seen_day = False

        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            plain = self._markdown_plain_text(line)

            output_match = OUTPUT_RE.search(plain)
            if output_match and pending_day in positioned:
                positioned[pending_day]["expected_output"] = output_match.group(1).strip()
                continue

            day_match = DAY_RE.search(plain)
            if not day_match:
                continue
            day = int(day_match.group(1))
            ordinal_match = re.match(r"^\s*(\d+)\.\s+", raw_line)
            local_ordinal = int(ordinal_match.group(1)) if ordinal_match else None
            if not seen_day:
                seen_day = True
                week_index = 0
            elif local_ordinal == 1:
                week_index += 1

            module = next(
                (title for start, end, title in module_ranges if start <= day <= end),
                "Uncategorized Module",
            )
            week = (
                week_titles[week_index]
                if 0 <= week_index < len(week_titles)
                else "Uncategorized Week"
            )
            pending_day = day
            positioned[day] = {
                "title": day_match.group(2).strip(" :-–—"),
                "module": module,
                "week": week,
                "expected_output": "",
            }

        repaired = []
        for lesson in lessons:
            correct = positioned.get(lesson.day)
            if not correct:
                repaired.append(lesson)
                continue
            repaired.append(
                CourseLesson(
                    day=lesson.day,
                    title=correct["title"] or lesson.title,
                    expected_output=correct["expected_output"] or lesson.expected_output,
                    module=correct["module"],
                    week=correct["week"],
                    article_url=lesson.article_url,
                    curriculum_url=lesson.curriculum_url,
                    order=lesson.order,
                )
            )
        return repaired

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

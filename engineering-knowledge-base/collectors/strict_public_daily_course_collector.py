from __future__ import annotations

import re
from urllib.parse import urljoin

from collectors.reader_backed_substack_course_collector import (
    DETAILED_CURRICULUM_MARKERS,
    EXTRA_PAYWALL_MARKERS,
    MARKDOWN_LINK_RE,
)
from collectors.substack_course_collector import (
    ArticleSnapshot,
    CourseLesson,
    DAY_RE,
    OUTPUT_RE,
    PAYWALL_MARKERS,
)
from collectors.anonymous_reader_daily_course_collector import (
    AnonymousReaderDailyCourseCollector,
)


class StrictPublicDailyCourseCollector(AnonymousReaderDailyCourseCollector):
    """Apply one conservative public boundary regardless of fetch transport.

    A lesson is retained as a full public article only when the fetched article
    itself has no paywall marker and contains enough material. Otherwise only
    the public introductory preview is retained. This intentionally avoids
    fixed day-number assumptions because Substack access can vary by article,
    account, campaign, and time.
    """

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
        return self._respect_article_access(
            snapshot,
            min_public_chars=min_public_chars,
            min_preview_chars=min_preview_chars,
        )

    def _article_from_reader_markdown(
        self,
        raw: str,
        article_url: str,
        *,
        min_public_chars: int,
        min_preview_chars: int,
    ) -> ArticleSnapshot:
        # Parse the anonymous reader response directly so classification is
        # based on the article's real paywall markers, not on a fixed day range.
        title_match = re.search(r"(?mi)^Title:\s*(.+)$", raw)
        published_match = re.search(r"(?mi)^Published Time:\s*(.+)$", raw)
        content = (
            raw.split("Markdown Content:", 1)[1].strip()
            if "Markdown Content:" in raw
            else raw.strip()
        )
        lowered = content.lower()
        explicit_paywall = any(
            marker in lowered for marker in (*PAYWALL_MARKERS, *EXTRA_PAYWALL_MARKERS)
        )
        content = self._truncate_public_markdown(content)
        links = tuple(
            dict.fromkeys(
                urljoin(article_url, href)
                for _label, href in MARKDOWN_LINK_RE.findall(content)
                if not href.startswith("#")
            )
        )
        if len(content) < min_preview_chars:
            snapshot = ArticleSnapshot(
                title=title_match.group(1).strip() if title_match else None,
                content="",
                published_date=published_match.group(1).strip() if published_match else None,
                links=tuple(),
                access_level="curriculum-only",
                explicit_paywall=explicit_paywall,
            )
        else:
            snapshot = ArticleSnapshot(
                title=title_match.group(1).strip() if title_match else None,
                content=content,
                published_date=published_match.group(1).strip() if published_match else None,
                links=links,
                access_level=(
                    "preview"
                    if explicit_paywall or len(content) < min_public_chars
                    else "public"
                ),
                explicit_paywall=explicit_paywall,
            )
        return self._respect_article_access(
            snapshot,
            min_public_chars=min_public_chars,
            min_preview_chars=min_preview_chars,
        )

    def _respect_article_access(
        self,
        snapshot: ArticleSnapshot,
        *,
        min_public_chars: int,
        min_preview_chars: int,
    ) -> ArticleSnapshot:
        if not snapshot.content or snapshot.access_level == "curriculum-only":
            return snapshot

        # Keep a complete article only when the fetched page itself did not
        # announce a paywall and enough material was visible anonymously.
        if not snapshot.explicit_paywall and len(snapshot.content) >= min_public_chars:
            return ArticleSnapshot(
                title=snapshot.title,
                content=snapshot.content,
                published_date=snapshot.published_date,
                links=snapshot.links,
                access_level="public",
                explicit_paywall=False,
            )

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
            ordinal_match = re.match(r"^\s*(\d+)\.\s+", raw_line)
            if ordinal_match is None:
                # Ignore prose such as "Integrate Day 8 to Day 14".
                pending_day = None
                continue
            day = int(day_match.group(1))
            local_ordinal = int(ordinal_match.group(1))
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

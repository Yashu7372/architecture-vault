from __future__ import annotations

from urllib.parse import urljoin, urlparse
import re

import requests

from collectors.substack_course_collector import (
    ArticleSnapshot,
    CourseLesson,
    DAY_RE,
    OUTPUT_RE,
    PAYWALL_MARKERS,
    SubstackCourseCollector,
)


MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
ARTICLE_END_MARKERS = (
    "#### discussion about this post",
    "### ready for more?",
    "\nprevious next",
)
EXTRA_PAYWALL_MARKERS = (
    "continue reading this post for free",
    "claim my free post",
    "or purchase a paid subscription",
)


class ReaderBackedSubstackCourseCollector(SubstackCourseCollector):
    """Use Jina Reader only when direct public Substack requests are blocked."""

    def __init__(self, session: requests.Session | None = None):
        super().__init__(session)
        self._active_source: dict = {}

    def collect(self, source: dict):
        self._active_source = source
        return super().collect(source)

    def discover_lessons(self, source: dict) -> list[CourseLesson]:
        try:
            return super().discover_lessons(source)
        except requests.RequestException as direct_error:
            if not source.get("reader_fallback", True):
                raise
            markdown = self._reader_fetch(source["url"], direct_error)
            lessons = self._discover_lessons_from_markdown(markdown, source)
            if not lessons:
                raise ValueError(
                    f"No Day N curriculum lessons found at {source['url']} through Jina Reader"
                )
            return lessons

    def _extract_public_article(
        self,
        article_url: str | None,
        *,
        min_public_chars: int,
        min_preview_chars: int,
    ) -> ArticleSnapshot:
        if not article_url:
            return super()._extract_public_article(
                article_url,
                min_public_chars=min_public_chars,
                min_preview_chars=min_preview_chars,
            )
        try:
            return super()._extract_public_article(
                article_url,
                min_public_chars=min_public_chars,
                min_preview_chars=min_preview_chars,
            )
        except requests.RequestException as direct_error:
            if not self._active_source.get("reader_fallback", True):
                raise
            markdown = self._reader_fetch(article_url, direct_error)
            return self._article_from_reader_markdown(
                markdown,
                article_url,
                min_public_chars=min_public_chars,
                min_preview_chars=min_preview_chars,
            )

    def _reader_fetch(self, target_url: str, direct_error: Exception) -> str:
        reader_url = f"https://r.jina.ai/{target_url}"
        headers = {
            "Accept": "text/plain",
            "X-No-Cache": "true",
            "X-With-Generated-Alt": "true",
        }
        try:
            response = self.session.get(
                reader_url,
                timeout=int(self._active_source.get("reader_timeout", 90)),
                headers=headers,
            )
            response.raise_for_status()
            return response.text
        except Exception as reader_error:
            raise RuntimeError(
                f"Direct public fetch failed for {target_url}: {direct_error}; "
                f"Jina Reader fallback failed: {reader_error}"
            ) from reader_error

    def _discover_lessons_from_markdown(self, markdown: str, source: dict) -> list[CourseLesson]:
        curriculum_url = source["url"]
        module = "Uncategorized Module"
        week = "Uncategorized Week"
        by_day: dict[int, CourseLesson] = {}
        pending_day: int | None = None

        for raw_line in markdown.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            plain = self._markdown_plain_text(line)
            heading = plain.lstrip("# ").strip()
            lower_heading = heading.lower()
            if lower_heading.startswith("module "):
                module = heading
                continue
            if lower_heading.startswith("week "):
                week = heading
                continue

            output_match = OUTPUT_RE.search(plain)
            if output_match and pending_day in by_day:
                existing = by_day[pending_day]
                by_day[pending_day] = CourseLesson(
                    day=existing.day,
                    title=existing.title,
                    expected_output=output_match.group(1).strip(),
                    module=existing.module,
                    week=existing.week,
                    article_url=existing.article_url,
                    curriculum_url=existing.curriculum_url,
                    order=0,
                )
                continue

            match = DAY_RE.search(plain)
            if not match:
                continue
            day = int(match.group(1))
            if source.get("start_day") and day < int(source["start_day"]):
                continue
            if source.get("end_day") and day > int(source["end_day"]):
                continue
            pending_day = day

            article_url = None
            for _label, href in MARKDOWN_LINK_RE.findall(line):
                absolute = urljoin(curriculum_url, href)
                parsed = urlparse(absolute)
                if parsed.path.startswith("/p/") or "open.substack.com" in parsed.netloc:
                    article_url = self._canonical_url(absolute)
                    break

            title = match.group(2).strip(" :-–—")
            title = re.sub(r"\s+\*+$", "", title).strip()
            candidate = CourseLesson(
                day=day,
                title=title,
                expected_output="",
                module=module,
                week=week,
                article_url=article_url,
                curriculum_url=curriculum_url,
                order=0,
            )
            existing = by_day.get(day)
            if existing is None or (not existing.article_url and candidate.article_url):
                by_day[day] = candidate

        ordered = []
        for order, day in enumerate(sorted(by_day), start=1):
            lesson = by_day[day]
            ordered.append(
                CourseLesson(
                    day=lesson.day,
                    title=lesson.title,
                    expected_output=lesson.expected_output,
                    module=lesson.module,
                    week=lesson.week,
                    article_url=lesson.article_url,
                    curriculum_url=lesson.curriculum_url,
                    order=order,
                )
            )
        return ordered

    def _article_from_reader_markdown(
        self,
        raw: str,
        article_url: str,
        *,
        min_public_chars: int,
        min_preview_chars: int,
    ) -> ArticleSnapshot:
        title_match = re.search(r"(?mi)^Title:\s*(.+)$", raw)
        published_match = re.search(r"(?mi)^Published Time:\s*(.+)$", raw)
        content = raw.split("Markdown Content:", 1)[1].strip() if "Markdown Content:" in raw else raw.strip()
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
            access_level = "curriculum-only"
            content = ""
        elif explicit_paywall or len(content) < min_public_chars:
            access_level = "preview"
        else:
            access_level = "public"
        return ArticleSnapshot(
            title=title_match.group(1).strip() if title_match else None,
            content=content,
            published_date=published_match.group(1).strip() if published_match else None,
            links=links,
            access_level=access_level,
            explicit_paywall=explicit_paywall,
        )

    @staticmethod
    def _truncate_public_markdown(content: str) -> str:
        lowered = content.lower()
        boundaries = []
        for marker in (*PAYWALL_MARKERS, *EXTRA_PAYWALL_MARKERS, *ARTICLE_END_MARKERS):
            index = lowered.find(marker)
            if index >= 0:
                boundaries.append(index)
        if boundaries:
            content = content[: min(boundaries)]
        return content.strip()

    @staticmethod
    def _markdown_plain_text(line: str) -> str:
        text = MARKDOWN_LINK_RE.sub(lambda match: match.group(1), line)
        text = re.sub(r"^[#>*\s\-+\d.]+", "", text)
        return re.sub(r"[*_`]+", "", text).strip()

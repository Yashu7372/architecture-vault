from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urlunparse
import re

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from slugify import slugify

from collectors.base import BaseCollector, KnowledgeDocument
from collectors.course_learning_builder import build_course_study_guide, infer_topic_tags
from collectors.web_collector import DEFAULT_HEADERS


DAY_RE = re.compile(r"\bDay\s+(\d+)\s*:?\s*(.+?)(?=\s+Output:|$)", re.IGNORECASE)
OUTPUT_RE = re.compile(r"\bOutput:\s*(.+)$", re.IGNORECASE)
PAYWALL_MARKERS = (
    "this post is for paid subscribers",
    "upgrade to paid to read the rest",
    "subscribe to continue reading",
    "paid subscribers only",
    "unlock this post",
    "become a paid subscriber",
)


@dataclass(frozen=True)
class CourseLesson:
    day: int
    title: str
    expected_output: str
    module: str
    week: str
    article_url: str | None
    curriculum_url: str
    order: int


@dataclass(frozen=True)
class ArticleSnapshot:
    title: str | None
    content: str
    published_date: str | None
    links: tuple[str, ...]
    access_level: str
    explicit_paywall: bool


class SubstackCourseCollector(BaseCollector):
    """Collect ordered public curriculum lessons without bypassing subscriber access."""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.last_report: dict = {}

    def collect(self, source: dict) -> list[KnowledgeDocument]:
        lessons = self.discover_lessons(source)
        skip_urls = {self._canonical_url(value, keep_fragment=True) for value in source.get("skip_urls", [])}
        eligible = [lesson for lesson in lessons if self._lesson_url(lesson) not in skip_urls]

        max_lessons = int(source.get("max_articles", source.get("max_lessons", len(eligible))))
        attempted = eligible[:max_lessons]
        min_public_chars = int(source.get("min_public_chars", 600))
        min_preview_chars = int(source.get("min_preview_chars", 120))

        documents: list[KnowledgeDocument] = []
        results: list[dict] = []
        counts = {"public": 0, "preview": 0, "curriculum-only": 0, "failed": 0}

        for lesson in attempted:
            previous_lesson = lessons[lesson.order - 2] if lesson.order > 1 else None
            next_lesson = lessons[lesson.order] if lesson.order < len(lessons) else None

            try:
                snapshot = self._extract_public_article(
                    lesson.article_url,
                    min_public_chars=min_public_chars,
                    min_preview_chars=min_preview_chars,
                )
                access_level = snapshot.access_level
                counts[access_level] += 1

                public_section = self._public_source_section(snapshot, lesson)
                study_guide = build_course_study_guide(
                    lesson=lesson,
                    previous_lesson=previous_lesson,
                    next_lesson=next_lesson,
                    public_content=snapshot.content,
                    access_level=access_level,
                )
                content = f"{public_section}\n\n---\n\n{study_guide}".strip()
                tags = list(
                    dict.fromkeys(
                        [
                            *source.get("tags", []),
                            slugify(lesson.module),
                            slugify(lesson.week),
                            *infer_topic_tags(lesson.title),
                        ]
                    )
                )
                tags = [tag for tag in tags if tag]

                metadata = {
                    "course_name": source["name"],
                    "course_track": source.get("track", "unspecified"),
                    "curriculum_url": lesson.curriculum_url,
                    "curriculum_day": lesson.day,
                    "curriculum_order": lesson.order,
                    "catalog_order": lesson.order,
                    "catalog_section": lesson.module,
                    "catalog_subsection": lesson.week,
                    "course_module": lesson.module,
                    "course_week": lesson.week,
                    "expected_output": lesson.expected_output,
                    "article_url": lesson.article_url,
                    "access_level": access_level,
                    "explicit_paywall": snapshot.explicit_paywall,
                    "public_content_chars": len(snapshot.content),
                    "generated_study_guide": True,
                    "previous_day": previous_lesson.day if previous_lesson else None,
                    "next_day": next_lesson.day if next_lesson else None,
                    "copyright_boundary": (
                        "Only curriculum metadata and content publicly visible without subscriber access were collected. "
                        "The stitched study guide is original explanatory material."
                    ),
                }
                title = f"Day {lesson.day}: {lesson.title}"
                document = KnowledgeDocument(
                    title=title,
                    url=self._lesson_url(lesson),
                    source_name=source["name"],
                    source_type="substack-course",
                    content=content,
                    author=source.get("author"),
                    published_date=snapshot.published_date,
                    tags=tags,
                    links=list(snapshot.links),
                    metadata=metadata,
                )
                documents.append(document)
                results.append(
                    {
                        "day": lesson.day,
                        "title": lesson.title,
                        "url": lesson.article_url or lesson.curriculum_url,
                        "document_url": document.url,
                        "status": access_level,
                        "content_chars": len(snapshot.content),
                    }
                )
            except Exception as exc:
                counts["failed"] += 1
                results.append(
                    {
                        "day": lesson.day,
                        "title": lesson.title,
                        "url": lesson.article_url or lesson.curriculum_url,
                        "document_url": self._lesson_url(lesson),
                        "status": "failed",
                        "error": str(exc),
                        "content_chars": 0,
                    }
                )

        self.last_report = {
            "catalog_url": source["url"],
            "course_track": source.get("track", "unspecified"),
            "discovered": len(lessons),
            "skipped_existing": len(lessons) - len(eligible),
            "attempted": len(attempted),
            "deferred_by_limit": max(0, len(eligible) - len(attempted)),
            "collected": len(documents),
            "failed": counts["failed"],
            "access_counts": {
                "public": counts["public"],
                "preview": counts["preview"],
                "curriculum-only": counts["curriculum-only"],
            },
            "results": results,
        }
        return documents

    def discover_lessons(self, source: dict) -> list[CourseLesson]:
        curriculum_url = source["url"]
        response = self.session.get(curriculum_url, timeout=45)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        article = soup.find("article") or soup

        module = "Uncategorized Module"
        week = "Uncategorized Week"
        by_day: dict[int, CourseLesson] = {}

        for node in article.find_all(["h2", "h3", "h4", "li"]):
            text = " ".join(node.stripped_strings).strip()
            if not text:
                continue
            if node.name == "h2" and text.lower().startswith("module "):
                module = text
                continue
            if node.name in {"h3", "h4"} and text.lower().startswith("week "):
                week = text
                continue
            if node.name != "li":
                continue

            match = DAY_RE.search(text)
            if not match:
                continue

            day = int(match.group(1))
            if source.get("start_day") and day < int(source["start_day"]):
                continue
            if source.get("end_day") and day > int(source["end_day"]):
                continue

            title = match.group(2).strip(" :-–—")
            output_match = OUTPUT_RE.search(text)
            expected_output = output_match.group(1).strip() if output_match else ""
            article_url = self._find_post_url(node, curriculum_url)

            candidate = CourseLesson(
                day=day,
                title=title,
                expected_output=expected_output,
                module=module,
                week=week,
                article_url=article_url,
                curriculum_url=curriculum_url,
                order=0,
            )
            existing = by_day.get(day)
            if existing is None or (not existing.article_url and candidate.article_url):
                by_day[day] = candidate

        ordered: list[CourseLesson] = []
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
        if not ordered:
            raise ValueError(f"No Day N curriculum lessons found at {curriculum_url}")
        return ordered

    def _extract_public_article(
        self,
        article_url: str | None,
        *,
        min_public_chars: int,
        min_preview_chars: int,
    ) -> ArticleSnapshot:
        if not article_url:
            return ArticleSnapshot(None, "", None, tuple(), "curriculum-only", False)

        response = self.session.get(article_url, timeout=45)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        full_text = " ".join(soup.stripped_strings).lower()
        explicit_paywall = any(marker in full_text for marker in PAYWALL_MARKERS)

        title_el = soup.find("h1")
        title = title_el.get_text(" ", strip=True) if title_el else None
        time_el = soup.find("time")
        published_date = None
        if time_el:
            published_date = time_el.get("datetime") or time_el.get_text(" ", strip=True)

        article = (
            soup.select_one("div.available-content")
            or soup.select_one("div.body.markup")
            or soup.find("article")
        )
        if article is None:
            return ArticleSnapshot(title, "", published_date, tuple(), "curriculum-only", explicit_paywall)

        for element in article.select(
            "script, style, nav, footer, aside, form, button, "
            "[class*='paywall'], [class*='subscription'], [class*='comment'], "
            "[data-testid*='paywall'], [data-testid*='subscribe']"
        ):
            element.decompose()

        content = md(str(article), heading_style="ATX").strip()
        links = tuple(
            dict.fromkeys(
                urljoin(article_url, anchor["href"])
                for anchor in article.find_all("a", href=True)
                if not anchor["href"].startswith("#")
            )
        )

        if len(content) < min_preview_chars:
            access_level = "curriculum-only"
            content = ""
        elif explicit_paywall or len(content) < min_public_chars:
            access_level = "preview"
        else:
            access_level = "public"

        return ArticleSnapshot(title, content, published_date, links, access_level, explicit_paywall)

    @staticmethod
    def _find_post_url(node, curriculum_url: str) -> str | None:
        for anchor in node.find_all("a", href=True):
            absolute = urljoin(curriculum_url, anchor["href"])
            parsed = urlparse(absolute)
            if parsed.path.startswith("/p/") or "open.substack.com" in parsed.netloc:
                return SubstackCourseCollector._canonical_url(absolute)
        return None

    @staticmethod
    def _public_source_section(snapshot: ArticleSnapshot, lesson: CourseLesson) -> str:
        boundary = (
            "> Access boundary: this section contains only text visible without subscriber access. "
            "No authentication, paywall bypass, or hidden-content extraction is used."
        )
        if snapshot.content:
            label = "Public Article Content" if snapshot.access_level == "public" else "Public Article Preview"
            return f"## {label}\n\n{boundary}\n\n{snapshot.content}"
        return (
            "## Public Curriculum Record\n\n"
            f"{boundary}\n\n"
            f"- Lesson: Day {lesson.day} — {lesson.title}\n"
            f"- Expected output: {lesson.expected_output or 'Not listed'}\n"
            f"- Article: {lesson.article_url or 'No article URL published in the curriculum'}"
        )

    @staticmethod
    def _lesson_url(lesson: CourseLesson) -> str:
        base = lesson.article_url or lesson.curriculum_url
        parsed = urlparse(base)
        fragment = f"curriculum-day-{lesson.day:03d}"
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/") or "/", "", "", fragment))

    @staticmethod
    def _canonical_url(url: str, keep_fragment: bool = False) -> str:
        parsed = urlparse(url.strip())
        fragment = parsed.fragment if keep_fragment else ""
        path = parsed.path.rstrip("/") or "/"
        return urlunparse(("https", parsed.netloc.lower(), path, "", "", fragment))

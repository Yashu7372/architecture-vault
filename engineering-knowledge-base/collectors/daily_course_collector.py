from __future__ import annotations

from slugify import slugify

from collectors.base import KnowledgeDocument
from collectors.course_completion_engine import complete_course_lesson
from collectors.course_learning_builder import infer_topic_tags
from collectors.substack_course_collector import SubstackCourseCollector


class DailyCourseCollector(SubstackCourseCollector):
    """Collect public lesson fragments and generate a separate original completed lesson."""

    def collect(self, source: dict) -> list[KnowledgeDocument]:
        lessons = self.discover_lessons(source)
        skip_urls = {self._canonical_url(value, keep_fragment=True) for value in source.get("skip_urls", [])}
        eligible = [lesson for lesson in lessons if self._lesson_url(lesson) not in skip_urls]
        max_lessons = int(source.get("max_articles", source.get("max_lessons", len(eligible))))
        attempted = eligible[:max_lessons]
        min_public_chars = int(source.get("min_public_chars", 600))
        min_preview_chars = int(source.get("min_preview_chars", 120))
        course_track = source.get("track", "unspecified")

        documents: list[KnowledgeDocument] = []
        results: list[dict] = []
        counts = {
            "public": 0,
            "preview": 0,
            "curriculum-only": 0,
            "failed": 0,
            "llm": 0,
            "deterministic-template": 0,
            "deterministic-fallback": 0,
        }

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

                completion = complete_course_lesson(
                    lesson=lesson,
                    previous_lesson=previous_lesson,
                    next_lesson=next_lesson,
                    public_content=snapshot.content,
                    access_level=access_level,
                    course_track=course_track,
                    session=self.session,
                )
                counts[completion.mode] += 1

                public_section = self._part_one(snapshot, lesson)
                content = f"{public_section}\n\n---\n\n{completion.content}".strip()
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
                    "course_track": course_track,
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
                    "lesson_completion_mode": completion.mode,
                    "lesson_completion_model": completion.model,
                    "lesson_completion_error": completion.error,
                    "generated_original_lesson": True,
                    "previous_day": previous_lesson.day if previous_lesson else None,
                    "next_day": next_lesson.day if next_lesson else None,
                    "copyright_boundary": (
                        "Part 1 contains only content publicly visible without subscriber access. "
                        "Part 2 is original educational material based on public curriculum signals and general engineering knowledge."
                    ),
                }
                document = KnowledgeDocument(
                    title=f"Day {lesson.day}: {lesson.title}",
                    url=self._lesson_url(lesson),
                    source_name=source["name"],
                    source_type="substack-daily-course",
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
                        "status": "collected",
                        "access_level": access_level,
                        "completion_mode": completion.mode,
                        "completion_model": completion.model,
                        "completion_error": completion.error,
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

        curriculum = [
            {
                "day": lesson.day,
                "order": lesson.order,
                "title": lesson.title,
                "expected_output": lesson.expected_output,
                "module": lesson.module,
                "week": lesson.week,
                "article_url": lesson.article_url,
                "curriculum_url": lesson.curriculum_url,
            }
            for lesson in lessons
        ]
        self.last_report = {
            "catalog_url": source["url"],
            "course_track": course_track,
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
            "completion_counts": {
                "llm": counts["llm"],
                "deterministic-template": counts["deterministic-template"],
                "deterministic-fallback": counts["deterministic-fallback"],
            },
            "curriculum": curriculum,
            "results": results,
        }
        return documents

    @classmethod
    def _part_one(cls, snapshot, lesson) -> str:
        source = cls._public_source_section(snapshot, lesson)
        if source.startswith("## Public Article Content"):
            source = source.replace("## Public Article Content", "### Public Article Content", 1)
        elif source.startswith("## Public Article Preview"):
            source = source.replace("## Public Article Preview", "### Public Article Preview", 1)
        elif source.startswith("## Public Curriculum Record"):
            source = source.replace("## Public Curriculum Record", "### Public Curriculum Record", 1)
        return (
            "## Part 1 — Public Source Capture\n\n"
            "> Saved exactly within the public-access boundary. Images remain as source URLs when the public page exposes them.\n\n"
            f"{source}"
        )

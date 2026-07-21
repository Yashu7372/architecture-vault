from __future__ import annotations

from collectors.anonymous_reader_daily_course_collector import (
    AnonymousReaderDailyCourseCollector,
)
from collectors.strict_public_daily_course_collector import (
    StrictPublicDailyCourseCollector,
)
from collectors.substack_course_collector import ArticleSnapshot


class PerPageAccessDailyCourseCollector(StrictPublicDailyCourseCollector):
    """Classify each lesson from the content actually visible on that page.

    No fixed Day range is assumed public. Direct Substack HTML and the anonymous
    reader fallback follow the same rule: retain full content only when no
    paywall marker is present; otherwise retain only the public introduction.
    """

    def _extract_public_article(
        self,
        article_url: str | None,
        *,
        min_public_chars: int,
        min_preview_chars: int,
    ) -> ArticleSnapshot:
        snapshot = AnonymousReaderDailyCourseCollector._extract_public_article(
            self,
            article_url,
            min_public_chars=min_public_chars,
            min_preview_chars=min_preview_chars,
        )
        return self._apply_actual_access_boundary(
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
        snapshot = AnonymousReaderDailyCourseCollector._article_from_reader_markdown(
            self,
            raw,
            article_url,
            min_public_chars=min_public_chars,
            min_preview_chars=min_preview_chars,
        )
        return self._apply_actual_access_boundary(
            snapshot,
            min_public_chars=min_public_chars,
            min_preview_chars=min_preview_chars,
        )

    def _apply_actual_access_boundary(
        self,
        snapshot: ArticleSnapshot,
        *,
        min_public_chars: int,
        min_preview_chars: int,
    ) -> ArticleSnapshot:
        if (
            snapshot.access_level == "public"
            and not snapshot.explicit_paywall
            and len(snapshot.content) >= min_public_chars
        ):
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

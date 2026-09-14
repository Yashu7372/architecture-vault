from __future__ import annotations

from collectors.reader_backed_daily_course_collector import (
    ReaderBackedDailyCourseCollector,
)


class AnonymousReaderDailyCourseCollector(ReaderBackedDailyCourseCollector):
    """Reader-backed daily collector using only anonymous public API features."""

    def _reader_fetch(self, target_url: str, direct_error: Exception) -> str:
        reader_url = f"https://r.jina.ai/{target_url}"
        try:
            response = self.session.get(
                reader_url,
                timeout=int(self._active_source.get("reader_timeout", 90)),
                headers={"Accept": "text/plain"},
            )
            response.raise_for_status()
            return response.text
        except Exception as reader_error:
            raise RuntimeError(
                f"Direct public fetch failed for {target_url}: {direct_error}; "
                f"anonymous Jina Reader fallback failed: {reader_error}"
            ) from reader_error

from __future__ import annotations

import time

from collectors.reader_backed_daily_course_collector import (
    ReaderBackedDailyCourseCollector,
)


class AnonymousReaderDailyCourseCollector(ReaderBackedDailyCourseCollector):
    """Reader-backed daily collector using only anonymous public API features."""

    def __init__(self, session=None):
        super().__init__(session)
        self._last_reader_request_at = 0.0

    def _reader_fetch(self, target_url: str, direct_error: Exception) -> str:
        reader_url = f"https://r.jina.ai/{target_url}"
        timeout = int(self._active_source.get("reader_timeout", 90))
        attempts = int(self._active_source.get("reader_max_retries", 6))
        min_interval = float(self._active_source.get("reader_min_interval_seconds", 2.5))
        base_backoff = float(self._active_source.get("reader_retry_backoff_seconds", 5.0))
        last_error: Exception | None = None

        for attempt in range(attempts):
            elapsed = time.monotonic() - self._last_reader_request_at
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)

            try:
                response = self.session.get(
                    reader_url,
                    timeout=timeout,
                    headers={"Accept": "text/plain"},
                )
                self._last_reader_request_at = time.monotonic()
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else base_backoff * (2**attempt)
                    last_error = RuntimeError(f"429 Too Many Requests; retrying after {delay:g}s")
                    time.sleep(delay)
                    continue
                response.raise_for_status()
                return response.text
            except Exception as reader_error:
                self._last_reader_request_at = time.monotonic()
                last_error = reader_error
                if attempt + 1 < attempts:
                    time.sleep(base_backoff * (2**attempt))
                    continue

        raise RuntimeError(
            f"Direct public fetch failed for {target_url}: {direct_error}; "
            f"anonymous Jina Reader fallback failed after {attempts} attempts: {last_error}"
        ) from last_error

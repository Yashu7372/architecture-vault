from __future__ import annotations

import html
import json
import re
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from playwright.sync_api import Page, sync_playwright
from youtube_transcript_api import YouTubeTranscriptApi

from collectors.base import BaseCollector, KnowledgeDocument


class YouTubeCollector(BaseCollector):
    """
    YouTube collector supporting:

      - youtube.com/watch?v=...
      - youtu.be/...
      - youtube.com/shorts/...
      - youtube.com/playlist?list=...

    Video content:
      - title / channel through YouTube oEmbed
      - transcript through youtube-transcript-api
      - timestamped Markdown transcript

    Playlist discovery:
      - Playwright only for expanding the playlist into video IDs

    No video files are downloaded.
    """

    def __init__(self):
        self.last_report: dict = {}
        self.transcript_api = YouTubeTranscriptApi()

    def collect(
        self,
        source: dict,
    ) -> list[KnowledgeDocument]:
        source_url = source["url"]

        skip_urls = {
            self._canonical_video_url(
                video_id
            )
            for video_id in (
                self._extract_video_id(url)
                for url in source.get(
                    "skip_urls",
                    [],
                )
            )
            if video_id
        }

        languages = source.get(
            "languages",
            ["en"],
        )

        max_videos = source.get(
            "max_videos",
            source.get("max_articles"),
        )

        source_kind = self._detect_url_type(
            source_url
        )

        if source_kind == "playlist":
            video_ids = self._discover_playlist_videos(
                source_url,
                source,
            )
        else:
            video_id = self._extract_video_id(
                source_url
            )

            if not video_id:
                raise ValueError(
                    f"Unsupported YouTube URL: {source_url}"
                )

            video_ids = [video_id]

        video_ids = self._deduplicate(video_ids)

        self.last_report = {
            "source_name": source.get("name"),
            "catalog_url": source_url,
            "source_kind": source_kind,
            "discovered": len(video_ids),
            "skipped_existing": 0,
            "attempted": 0,
            "deferred_by_limit": 0,
            "collected": 0,
            "failed": 0,
            "results": [],
        }

        pending_ids: list[str] = []

        for video_id in video_ids:
            canonical_url = self._canonical_video_url(
                video_id
            )

            if canonical_url in skip_urls:
                self.last_report[
                    "skipped_existing"
                ] += 1

                self.last_report[
                    "results"
                ].append(
                    {
                        "url": canonical_url,
                        "status": "skipped_existing",
                        "content_chars": 0,
                    }
                )

                continue

            pending_ids.append(video_id)

        if max_videos is not None:
            max_videos = max(
                0,
                int(max_videos),
            )

            self.last_report[
                "deferred_by_limit"
            ] = max(
                0,
                len(pending_ids) - max_videos,
            )

            pending_ids = pending_ids[
                :max_videos
            ]

        docs: list[KnowledgeDocument] = []

        for video_id in pending_ids:
            self.last_report[
                "attempted"
            ] += 1

            try:
                doc = self._collect_video(
                    video_id=video_id,
                    source=source,
                    languages=languages,
                )

                docs.append(doc)

                self.last_report[
                    "collected"
                ] += 1

                self.last_report[
                    "results"
                ].append(
                    {
                        "url": doc.url,
                        "title": doc.title,
                        "status": "collected",
                        "content_chars": len(
                            doc.content
                        ),
                    }
                )

                print(
                    f"YouTube collected: "
                    f"{doc.title}"
                )

            except Exception as exc:
                canonical_url = (
                    self._canonical_video_url(
                        video_id
                    )
                )

                self.last_report[
                    "failed"
                ] += 1

                self.last_report[
                    "results"
                ].append(
                    {
                        "url": canonical_url,
                        "status": "failed",
                        "error": str(exc),
                        "content_chars": 0,
                    }
                )

                print(
                    f"Failed YouTube video "
                    f"{canonical_url}: {exc}"
                )

        return docs

    def _collect_video(
        self,
        video_id: str,
        source: dict,
        languages: list[str],
    ) -> KnowledgeDocument:
        canonical_url = (
            self._canonical_video_url(
                video_id
            )
        )

        metadata = self._fetch_oembed_metadata(
            canonical_url
        )

        title = (
            metadata.get("title")
            or f"YouTube Video {video_id}"
        )

        author = metadata.get(
            "author_name"
        )

        transcript_content = ""
        transcript_metadata: dict = {}

        try:
            transcript = (
                self.transcript_api.fetch(
                    video_id,
                    languages=languages,
                )
            )

            transcript_content = (
                self._transcript_to_markdown(
                    transcript
                )
            )

            transcript_metadata = {
                "transcript_available": True,
                "transcript_language": getattr(
                    transcript,
                    "language",
                    None,
                ),
                "transcript_language_code": getattr(
                    transcript,
                    "language_code",
                    None,
                ),
                "transcript_generated": getattr(
                    transcript,
                    "is_generated",
                    None,
                ),
                "transcript_snippets": len(
                    transcript
                ),
            }

        except Exception as exc:
            transcript_metadata = {
                "transcript_available": False,
                "transcript_error": (
                    f"{type(exc).__name__}: {exc}"
                ),
            }

            transcript_content = (
                "## Transcript\n\n"
                "_Transcript is not available "
                "for this video._"
            )

        content_parts = [
            "## Video",
            "",
            f"- URL: {canonical_url}",
        ]

        if author:
            content_parts.append(
                f"- Channel: {author}"
            )

        content_parts.extend(
            [
                "",
                transcript_content,
            ]
        )

        return KnowledgeDocument(
            title=title,
            url=canonical_url,
            source_name=source["name"],
            source_type="youtube",
            content="\n".join(content_parts),
            author=author,
            tags=source.get(
                "tags",
                ["youtube"],
            ),
            links=[canonical_url],
            metadata={
                "video_id": video_id,
                "youtube_kind": (
                    "short"
                    if "/shorts/" in source["url"]
                    else "video"
                ),
                **transcript_metadata,
            },
        )

    def _discover_playlist_videos(
        self,
        playlist_url: str,
        source: dict,
    ) -> list[str]:
        headless = bool(
            source.get(
                "headless",
                True,
            )
        )

        max_scrolls = int(
            source.get(
                "max_scrolls",
                80,
            )
        )

        print(
            f"Discovering YouTube playlist: "
            f"{playlist_url}"
        )

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=headless
            )

            try:
                page = browser.new_page(
                    viewport={
                        "width": 1440,
                        "height": 1000,
                    }
                )

                page.goto(
                    playlist_url,
                    wait_until="domcontentloaded",
                    timeout=90_000,
                )

                page.wait_for_timeout(2500)

                self._scroll_playlist(
                    page,
                    max_scrolls=max_scrolls,
                )

                hrefs = page.locator(
                    'a[href*="watch?v="]'
                ).evaluate_all(
                    """
                    elements =>
                        elements.map(
                            element =>
                                element.getAttribute('href')
                        )
                    """
                )

            finally:
                browser.close()

        playlist_id = self._extract_playlist_id(
            playlist_url
        )

        video_ids: list[str] = []

        for href in hrefs:
            if not href:
                continue

            parsed = urlparse(href)
            params = parse_qs(
                parsed.query
            )

            video_id = (
                params.get(
                    "v",
                    [None],
                )[0]
            )

            href_playlist_id = (
                params.get(
                    "list",
                    [None],
                )[0]
            )

            # Keep playlist entries, not random
            # recommendation links.
            if (
                playlist_id
                and href_playlist_id
                and href_playlist_id
                != playlist_id
            ):
                continue

            if video_id:
                video_ids.append(
                    video_id
                )

        return self._deduplicate(
            video_ids
        )

    @staticmethod
    def _scroll_playlist(
        page: Page,
        max_scrolls: int,
    ) -> None:
        previous_count = -1
        stable_iterations = 0

        for _ in range(max_scrolls):
            count = page.locator(
                'a[href*="watch?v="]'
            ).count()

            if count == previous_count:
                stable_iterations += 1

                if stable_iterations >= 4:
                    break
            else:
                stable_iterations = 0

            previous_count = count

            page.mouse.wheel(
                0,
                5000,
            )

            page.wait_for_timeout(
                700
            )

    @staticmethod
    def _fetch_oembed_metadata(
        video_url: str,
    ) -> dict:
        """
        Lightweight metadata retrieval without
        YouTube Data API credentials.
        """

        query = urlencode(
            {
                "url": video_url,
                "format": "json",
            }
        )

        request = Request(
            "https://www.youtube.com/oembed?"
            + query,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 "
                    "ArchitectureVault/1.0"
                )
            },
        )

        try:
            with urlopen(
                request,
                timeout=20,
            ) as response:
                payload = json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

            return {
                key: (
                    html.unescape(value)
                    if isinstance(
                        value,
                        str,
                    )
                    else value
                )
                for key, value
                in payload.items()
            }

        except Exception as exc:
            print(
                "YouTube metadata lookup "
                f"failed: {exc}"
            )

            return {}

    @staticmethod
    def _transcript_to_markdown(
        transcript,
    ) -> str:
        """
        Groups transcript snippets into
        ~60 second Markdown sections.

        This gives Architecture Vault's
        existing chunk/index pipeline better
        semantic boundaries than one huge
        transcript string.
        """

        sections: list[str] = []
        current_bucket = None
        current_text: list[str] = []

        for snippet in transcript:
            bucket = int(
                snippet.start // 60
            )

            if (
                current_bucket is not None
                and bucket
                != current_bucket
            ):
                sections.extend(
                    YouTubeCollector
                    ._render_transcript_bucket(
                        current_bucket,
                        current_text,
                    )
                )

                current_text = []

            current_bucket = bucket

            text = re.sub(
                r"\s+",
                " ",
                snippet.text,
            ).strip()

            if text:
                current_text.append(
                    text
                )

        if (
            current_bucket is not None
            and current_text
        ):
            sections.extend(
                YouTubeCollector
                ._render_transcript_bucket(
                    current_bucket,
                    current_text,
                )
            )

        if not sections:
            return (
                "## Transcript\n\n"
                "_Transcript contained no text._"
            )

        return (
            "## Transcript\n\n"
            + "\n".join(sections)
        )

    @staticmethod
    def _render_transcript_bucket(
        bucket: int,
        texts: list[str],
    ) -> list[str]:
        seconds = bucket * 60

        timestamp = (
            YouTubeCollector
            ._format_timestamp(
                seconds
            )
        )

        return [
            f"### {timestamp}",
            "",
            " ".join(texts),
            "",
        ]

    @staticmethod
    def _format_timestamp(
        seconds: int,
    ) -> str:
        hours, remainder = divmod(
            seconds,
            3600,
        )

        minutes, secs = divmod(
            remainder,
            60,
        )

        if hours:
            return (
                f"{hours:02d}:"
                f"{minutes:02d}:"
                f"{secs:02d}"
            )

        return (
            f"{minutes:02d}:"
            f"{secs:02d}"
        )

    @staticmethod
    def _detect_url_type(
        url: str,
    ) -> str:
        parsed = urlparse(url)

        params = parse_qs(
            parsed.query
        )

        if (
            "/playlist" in parsed.path
            or (
                "list" in params
                and "v" not in params
            )
        ):
            return "playlist"

        if "/shorts/" in parsed.path:
            return "short"

        return "video"

    @staticmethod
    def _extract_playlist_id(
        url: str,
    ) -> str | None:
        parsed = urlparse(url)

        return parse_qs(
            parsed.query
        ).get(
            "list",
            [None],
        )[0]

    @staticmethod
    def _extract_video_id(
        url: str,
    ) -> str | None:
        parsed = urlparse(url)

        host = parsed.netloc.lower()

        if host in (
            "youtu.be",
            "www.youtu.be",
        ):
            return (
                parsed.path
                .strip("/")
                .split("/")[0]
                or None
            )

        if "/shorts/" in parsed.path:
            parts = [
                part
                for part
                in parsed.path.split("/")
                if part
            ]

            try:
                index = parts.index(
                    "shorts"
                )

                return parts[
                    index + 1
                ]

            except (
                ValueError,
                IndexError,
            ):
                return None

        return parse_qs(
            parsed.query
        ).get(
            "v",
            [None],
        )[0]

    @staticmethod
    def _canonical_video_url(
        video_id: str,
    ) -> str:
        return (
            "https://www.youtube.com/"
            f"watch?v={video_id}"
        )

    @staticmethod
    def _deduplicate(
        values: list[str],
    ) -> list[str]:
        seen = set()
        result = []

        for value in values:
            if not value or value in seen:
                continue

            seen.add(value)
            result.append(value)

        return result
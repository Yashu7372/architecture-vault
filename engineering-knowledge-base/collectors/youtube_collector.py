from urllib.parse import parse_qs, urlparse

from youtube_transcript_api import YouTubeTranscriptApi

from collectors.base import BaseCollector, KnowledgeDocument


class YouTubeCollector(BaseCollector):
    def collect(self, source: dict) -> list[KnowledgeDocument]:
        video_id = self._video_id(source["url"])
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        lines = []
        for item in transcript:
            seconds = int(item.get("start", 0))
            minutes, second = divmod(seconds, 60)
            hours, minute = divmod(minutes, 60)
            timestamp = f"{hours:02d}:{minute:02d}:{second:02d}" if hours else f"{minute:02d}:{second:02d}"
            text = item.get("text", "").replace("\n", " ").strip()
            if text:
                lines.append(f"[{timestamp}] {text}")

        return [
            KnowledgeDocument(
                title=source.get("name", f"YouTube {video_id}"),
                url=source["url"],
                source_name=source.get("name", "youtube"),
                source_type="youtube",
                content="# Transcript\n\n" + "\n\n".join(lines),
                tags=source.get("tags", ["youtube"]),
                links=[source["url"]],
            )
        ]

    @staticmethod
    def _video_id(url: str) -> str:
        parsed = urlparse(url)
        if parsed.netloc.endswith("youtu.be"):
            return parsed.path.strip("/").split("/")[0]
        if "/shorts/" in parsed.path:
            return parsed.path.split("/shorts/", 1)[1].split("/", 1)[0]
        video_id = parse_qs(parsed.query).get("v", [None])[0]
        if not video_id:
            raise ValueError(f"Could not determine YouTube video id: {url}")
        return video_id

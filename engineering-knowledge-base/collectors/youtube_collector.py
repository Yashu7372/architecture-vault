from collectors.base import BaseCollector, KnowledgeDocument


class YouTubeCollector(BaseCollector):
    def collect(self, source: dict) -> list[KnowledgeDocument]:
        # Placeholder collector. Later this can be extended with YouTube Data API
        # or transcript extraction for videos where transcripts are available.
        return [
            KnowledgeDocument(
                title=source.get("name", "youtube-video"),
                url=source["url"],
                source_name=source.get("name", "youtube"),
                source_type="youtube",
                content="Add video summary, transcript notes, architecture concepts, and implementation learnings here.",
                tags=source.get("tags", ["youtube", "to-review"]),
                links=[source["url"]],
            )
        ]

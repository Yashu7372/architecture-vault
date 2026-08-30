from __future__ import annotations

import requests

from collectors.base import BaseCollector, KnowledgeDocument
from drivers.web_reader import DEFAULT_HEADERS, WebDocumentReader


class WebCollector(BaseCollector):
    """Bounded collector capability for public web sources."""

    def __init__(self, session: requests.Session | None = None):
        self.reader = WebDocumentReader(session)
        # Backward-compatible access for focused tests/extensions.
        self.session = self.reader.session

    def collect(self, source: dict) -> list[KnowledgeDocument]:
        article_urls = source.get("article_urls") or self.reader.discover_article_urls(source["url"])
        max_articles = int(source.get("max_articles", 50))
        min_content_chars = int(source.get("min_content_chars", 500))

        docs: list[KnowledgeDocument] = []
        for article_url in article_urls[:max_articles]:
            doc = self.extract_url(article_url, source)
            if doc and len(doc.content) >= min_content_chars:
                docs.append(doc)
        return docs

    def extract_url(self, article_url: str, source: dict) -> KnowledgeDocument | None:
        return self.reader.extract_url(article_url, source)

    def _discover_article_urls(self, start_url: str) -> list[str]:
        return self.reader.discover_article_urls(start_url)

    def _looks_like_article(self, url: str) -> bool:
        return self.reader.looks_like_article(url)

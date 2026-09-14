from urllib.parse import urljoin, urlparse
import re

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from readability import Document

from collectors.base import BaseCollector, KnowledgeDocument


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    )
}


class WebCollector(BaseCollector):
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def collect(self, source: dict) -> list[KnowledgeDocument]:
        article_urls = source.get("article_urls") or self._discover_article_urls(source["url"])
        max_articles = int(source.get("max_articles", 50))
        min_content_chars = int(source.get("min_content_chars", 500))

        docs: list[KnowledgeDocument] = []
        for article_url in article_urls[:max_articles]:
            doc = self.extract_url(article_url, source)
            if doc and len(doc.content) >= min_content_chars:
                docs.append(doc)
        return docs

    def _discover_article_urls(self, start_url: str) -> list[str]:
        response = self.session.get(start_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        base_domain = urlparse(start_url).netloc
        urls = set()
        for anchor in soup.find_all("a", href=True):
            href = urljoin(start_url, anchor["href"]).split("#")[0].split("?")[0]
            parsed = urlparse(href)
            if parsed.netloc == base_domain and self._looks_like_article(href):
                urls.add(href)
        return sorted(urls)

    def _looks_like_article(self, url: str) -> bool:
        lower = url.lower()
        blocked = ["/tag/", "/category/", "/author/", "/about", "/careers", "/privacy", "/terms", "/login"]
        if any(value in lower for value in blocked):
            return False
        return (
            "/blog/" in lower
            or "/engineering/" in lower
            or "/tech/" in lower
            or re.search(r"/20\d{2}/", lower) is not None
            or len(urlparse(url).path.strip("/").split("/")) >= 2
        )

    def extract_url(self, article_url: str, source: dict) -> KnowledgeDocument | None:
        try:
            response = self.session.get(article_url, timeout=30)
            response.raise_for_status()
            html = response.text
            readable = Document(html)
            title = readable.short_title() or source.get("title") or article_url
            content = md(readable.summary(), heading_style="ATX").strip()
            soup = BeautifulSoup(html, "html.parser")
            time_element = soup.find("time")
            published_date = (
                time_element.get("datetime") or time_element.get_text(" ", strip=True)
                if time_element
                else None
            )
            author = self._extract_author(soup)
            links = sorted(
                {
                    urljoin(article_url, anchor["href"])
                    for anchor in soup.find_all("a", href=True)
                    if anchor.get("href")
                }
            )
            return KnowledgeDocument(
                title=title,
                url=article_url,
                source_name=source["name"],
                source_type=source.get("document_type", "web"),
                content=content,
                author=author,
                published_date=published_date,
                tags=list(dict.fromkeys(source.get("tags", []))),
                links=links,
                metadata=dict(source.get("document_metadata", {})),
            )
        except Exception as exc:
            print(f"Failed web article {article_url}: {exc}")
            return None

    @staticmethod
    def _extract_author(soup: BeautifulSoup) -> str | None:
        author_meta = soup.find("meta", attrs={"name": "author"})
        if author_meta and author_meta.get("content"):
            return author_meta["content"].strip()
        author_property = soup.find("meta", attrs={"property": "article:author"})
        if author_property and author_property.get("content"):
            return author_property["content"].strip()
        return None

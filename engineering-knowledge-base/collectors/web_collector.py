from urllib.parse import urljoin, urlparse
import re
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from readability import Document

from collectors.base import BaseCollector, KnowledgeDocument


class WebCollector(BaseCollector):
    def collect(self, source: dict) -> list[KnowledgeDocument]:
        article_urls = self._discover_article_urls(source["url"])
        docs: list[KnowledgeDocument] = []
        for article_url in article_urls[:50]:
            doc = self._extract_article(article_url, source)
            if doc and len(doc.content) > 500:
                docs.append(doc)
        return docs

    def _discover_article_urls(self, start_url: str) -> list[str]:
        response = requests.get(start_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        base_domain = urlparse(start_url).netloc
        urls = set()
        for a in soup.find_all("a", href=True):
            href = urljoin(start_url, a["href"]).split("#")[0].split("?")[0]
            parsed = urlparse(href)
            if parsed.netloc == base_domain and self._looks_like_article(href):
                urls.add(href)
        return sorted(urls)

    def _looks_like_article(self, url: str) -> bool:
        lower = url.lower()
        blocked = ["/tag/", "/category/", "/author/", "/about", "/careers", "/privacy", "/terms", "/login"]
        if any(x in lower for x in blocked):
            return False
        return (
            "/blog/" in lower
            or "/engineering/" in lower
            or "/tech/" in lower
            or re.search(r"/20\d{2}/", lower) is not None
            or len(urlparse(url).path.strip("/").split("/")) >= 2
        )

    def _extract_article(self, article_url: str, source: dict) -> KnowledgeDocument | None:
        try:
            html = requests.get(article_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
            readable = Document(html)
            title = readable.short_title() or article_url
            content = md(readable.summary(), heading_style="ATX").strip()
            soup = BeautifulSoup(html, "html.parser")
            time_el = soup.find("time")
            published_date = time_el.get("datetime") or time_el.get_text(" ", strip=True) if time_el else None
            links = [urljoin(article_url, a["href"]) for a in soup.find_all("a", href=True)]
            return KnowledgeDocument(
                title=title,
                url=article_url,
                source_name=source["name"],
                source_type="web",
                content=content,
                published_date=published_date,
                tags=source.get("tags", []),
                links=links,
            )
        except Exception as exc:
            print(f"Failed web article {article_url}: {exc}")
            return None

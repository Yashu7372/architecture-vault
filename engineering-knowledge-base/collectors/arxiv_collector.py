from io import BytesIO
from urllib.parse import quote, urlparse
import re

import feedparser
import requests
from pypdf import PdfReader

from collectors.base import BaseCollector, KnowledgeDocument


class ArxivCollector(BaseCollector):
    def collect(self, source: dict) -> list[KnowledgeDocument]:
        if source.get("url"):
            arxiv_id = self._extract_id(source["url"])
            feed_url = f"https://export.arxiv.org/api/query?id_list={quote(arxiv_id)}"
        else:
            query = source["query"]
            max_results = source.get("max_results", 20)
            feed_url = (
                "https://export.arxiv.org/api/query?"
                f"search_query=all:{quote(query)}"
                f"&start=0&max_results={max_results}"
                "&sortBy=submittedDate&sortOrder=descending"
            )

        feed = feedparser.parse(feed_url)
        docs: list[KnowledgeDocument] = []
        for entry in feed.entries:
            title = entry.title.replace("\n", " ").strip()
            authors = ", ".join(author.name for author in entry.get("authors", []))
            summary = entry.summary.strip()
            paper_url = entry.link
            published = entry.published
            content = f"# Abstract\n\n{summary}\n\n## Authors\n\n{authors}\n"

            try:
                paper_id = self._extract_id(paper_url)
                full_text = self._extract_pdf_text(f"https://arxiv.org/pdf/{paper_id}.pdf")
                if full_text:
                    content += "\n\n# Full Paper\n" + full_text
            except Exception as exc:
                content += f"\n\n> Full PDF extraction unavailable: {exc}\n"

            docs.append(
                KnowledgeDocument(
                    title=title,
                    url=paper_url,
                    source_name=source["name"],
                    source_type="arxiv",
                    content=content,
                    author=authors,
                    published_date=published,
                    tags=source.get("tags", []),
                    links=[paper_url],
                )
            )
        return docs

    @staticmethod
    def _extract_id(url: str) -> str:
        path = urlparse(url).path.strip("/")
        match = re.search(r"(?:abs|pdf)/([^/]+)", "/" + path)
        if match:
            return match.group(1).removesuffix(".pdf")
        if re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", path):
            return path
        raise ValueError(f"Could not determine arXiv id from {url}")

    @staticmethod
    def _extract_pdf_text(url: str) -> str:
        response = requests.get(url, headers={"User-Agent": "engineering-knowledge-collector"}, timeout=60)
        response.raise_for_status()
        reader = PdfReader(BytesIO(response.content))
        sections = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            sections.append(f"\n\n## Page {page_number}\n\n{text}")
        return "".join(sections)

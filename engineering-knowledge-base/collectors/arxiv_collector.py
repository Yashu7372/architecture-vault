from urllib.parse import quote
import feedparser

from collectors.base import BaseCollector, KnowledgeDocument


class ArxivCollector(BaseCollector):
    def collect(self, source: dict) -> list[KnowledgeDocument]:
        query = source["query"]
        max_results = source.get("max_results", 20)
        url = (
            "https://export.arxiv.org/api/query?"
            f"search_query=all:{quote(query)}"
            f"&start=0&max_results={max_results}"
            "&sortBy=submittedDate&sortOrder=descending"
        )
        feed = feedparser.parse(url)
        docs: list[KnowledgeDocument] = []
        for entry in feed.entries:
            title = entry.title.replace("\n", " ").strip()
            authors = ", ".join(author.name for author in entry.get("authors", []))
            summary = entry.summary.strip()
            paper_url = entry.link
            published = entry.published
            content = f"""# Abstract\n\n{summary}\n\n## Authors\n\n{authors}\n\n## Paper Link\n\n{paper_url}\n"""
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

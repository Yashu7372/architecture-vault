from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse
import re

import requests
from slugify import slugify

from collectors.base import BaseCollector, KnowledgeDocument
from collectors.web_collector import DEFAULT_HEADERS, WebCollector


HEADING_RE = re.compile(r"^(#{2,6})\s+(.+?)\s*$")
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


@dataclass(frozen=True)
class CatalogEntry:
    title: str
    url: str
    section: str
    subsection: str
    order: int
    locations: tuple[tuple[str, str], ...]


class CatalogCollector(BaseCollector):
    """Collect article links from a Markdown catalog and extract every unique target page."""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.web_collector = WebCollector(self.session)

    def collect(self, source: dict) -> list[KnowledgeDocument]:
        entries = self.discover_entries(source)
        skip_urls = {self._canonical_url(url) for url in source.get("skip_urls", [])}
        entries = [entry for entry in entries if entry.url not in skip_urls]
        max_articles = int(source.get("max_articles", len(entries)))
        min_content_chars = int(source.get("min_content_chars", 500))
        docs: list[KnowledgeDocument] = []

        for entry in entries[:max_articles]:
            tags = list(source.get("tags", []))
            for section, subsection in entry.locations:
                tags.extend(self._section_tags(section, subsection))
            article_source = {
                **source,
                "document_type": "web",
                "title": entry.title,
                "tags": list(dict.fromkeys(tags)),
                "document_metadata": {
                    "catalog_name": source["name"],
                    "catalog_url": source.get("catalog_page", source["url"]),
                    "catalog_section": entry.section,
                    "catalog_subsection": entry.subsection,
                    "catalog_order": entry.order,
                    "catalog_link_title": entry.title,
                    "catalog_locations": [
                        {"section": section, "subsection": subsection}
                        for section, subsection in entry.locations
                    ],
                },
            }
            doc = self.web_collector.extract_url(entry.url, article_source)
            if not doc or len(doc.content) < min_content_chars:
                continue
            if source.get("prefer_catalog_title"):
                doc.title = entry.title
            doc.metadata["catalog_discovered_title"] = entry.title
            docs.append(doc)
        return docs

    def discover_entries(self, source: dict) -> list[CatalogEntry]:
        response = self.session.get(source["url"], timeout=30)
        response.raise_for_status()
        markdown = response.text
        allow_domains = {domain.lower() for domain in source.get("allow_domains", [])}
        include_sections = {section.lower() for section in source.get("include_sections", [])}

        section = "Uncategorized"
        subsection = "General"
        records: dict[str, dict] = {}

        for line in markdown.splitlines():
            stripped = line.strip()
            heading = HEADING_RE.match(stripped)
            if heading:
                level = len(heading.group(1))
                value = self._clean_heading(heading.group(2))
                if level == 2:
                    section = value
                    subsection = "General"
                elif level >= 3:
                    subsection = value
                continue

            if not stripped.startswith("-"):
                continue
            for link in LINK_RE.finditer(stripped):
                title, raw_url = link.groups()
                url = self._canonical_url(raw_url)
                domain = urlparse(url).netloc.lower()
                if allow_domains and domain not in allow_domains:
                    continue
                if include_sections and section.lower() not in include_sections:
                    continue

                location = (section, subsection)
                if url not in records:
                    records[url] = {
                        "title": title.strip(),
                        "url": url,
                        "section": section,
                        "subsection": subsection,
                        "order": len(records) + 1,
                        "locations": [location],
                    }
                elif location not in records[url]["locations"]:
                    records[url]["locations"].append(location)

        return [
            CatalogEntry(
                title=record["title"],
                url=record["url"],
                section=record["section"],
                subsection=record["subsection"],
                order=record["order"],
                locations=tuple(record["locations"]),
            )
            for record in records.values()
        ]

    @staticmethod
    def _clean_heading(value: str) -> str:
        return value.replace("\\#", "#").strip()

    @staticmethod
    def _canonical_url(url: str) -> str:
        parsed = urlparse(url.strip())
        scheme = "https" if parsed.scheme in {"http", "https"} else parsed.scheme
        path = parsed.path.rstrip("/") or "/"
        return urlunparse((scheme, parsed.netloc.lower(), path, "", "", ""))

    @staticmethod
    def _section_tags(section: str, subsection: str) -> list[str]:
        tags = []
        for value in (section, subsection):
            slug = slugify(value)
            if slug and slug not in {"general", "companies", "technologies", "interviews", "ai"}:
                tags.append(slug)
        return tags

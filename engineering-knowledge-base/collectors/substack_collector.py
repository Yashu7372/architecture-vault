from urllib.parse import urljoin, urlparse
import re

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from playwright.sync_api import sync_playwright

from collectors.base import BaseCollector, KnowledgeDocument


class SubstackCollector(BaseCollector):
    def __init__(self):
        self.last_report: dict = {}

    def collect(self, source: dict) -> list[KnowledgeDocument]:
        if source.get("course_mode"):
            from collectors.reader_backed_daily_course_collector import (
                ReaderBackedDailyCourseCollector,
            )

            collector = ReaderBackedDailyCourseCollector()
            documents = collector.collect(source)
            self.last_report = collector.last_report
            return documents

        docs: list[KnowledgeDocument] = []
        state_file = source.get("storage_state_file")
        headless = bool(source.get("headless", False))
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(storage_state=state_file) if state_file else browser.new_context()
            page = context.new_page()
            for url in self._discover_posts(page, source["url"]):
                doc = self._extract_post(page, url, source)
                if doc and len(doc.content) > 500:
                    docs.append(doc)
            browser.close()
        return docs

    def _discover_posts(self, page, start_url: str) -> list[str]:
        page.goto(start_url, wait_until="networkidle")
        page.wait_for_timeout(2000)
        for label in ["See all", "Load more", "More"]:
            try:
                button = page.get_by_text(label, exact=True)
                if button.count() > 0:
                    button.first.click()
                    page.wait_for_timeout(2000)
            except Exception:
                pass
        last_height = 0
        for _ in range(40):
            page.mouse.wheel(0, 3000)
            page.wait_for_timeout(800)
            height = page.evaluate("document.body.scrollHeight")
            if height == last_height:
                break
            last_height = height
        soup = BeautifulSoup(page.content(), "html.parser")
        base_domain = urlparse(start_url).netloc
        urls = set()
        for a in soup.find_all("a", href=True):
            href = urljoin(start_url, a["href"])
            parsed = urlparse(href)
            if parsed.netloc == base_domain and parsed.path.startswith("/p/"):
                urls.add(f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
        return sorted(urls)

    def _extract_post(self, page, url: str, source: dict) -> KnowledgeDocument | None:
        try:
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(1500)
            soup = BeautifulSoup(page.content(), "html.parser")
            title_el = soup.find("h1")
            title = title_el.get_text(" ", strip=True) if title_el else url
            time_el = soup.find("time")
            published_date = time_el.get_text(" ", strip=True) if time_el else None
            article_el = soup.find("article") or soup.find("div", class_=re.compile("body|post", re.I))
            if not article_el:
                return None
            content = md(str(article_el), heading_style="ATX").strip()
            links = [urljoin(url, a["href"]) for a in article_el.find_all("a", href=True)]
            return KnowledgeDocument(
                title=title,
                url=url,
                source_name=source["name"],
                source_type="substack",
                content=content,
                published_date=published_date,
                tags=source.get("tags", []),
                links=links,
            )
        except Exception as exc:
            print(f"Failed Substack post {url}: {exc}")
            return None

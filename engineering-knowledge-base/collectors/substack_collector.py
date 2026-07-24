from urllib.parse import urljoin, urlparse
import re

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from playwright.sync_api import sync_playwright

from collectors.base import BaseCollector, KnowledgeDocument


class SubstackCollector(BaseCollector):
    """Collect Substack publications, posts, Notes, and article-link timelines."""

    def collect(self, source: dict) -> list[KnowledgeDocument]:
        docs: list[KnowledgeDocument] = []
        state_file = source.get("storage_state_file")
        headless = source.get("headless", False)
        max_items = int(source.get("max_items", 100))

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = (
                browser.new_context(storage_state=state_file)
                if state_file
                else browser.new_context()
            )
            page = context.new_page()

            discovered = self._discover_urls(page, source)
            for url in discovered[:max_items]:
                doc = self._extract_document(page, url, source)
                if doc and len(doc.content) > 300:
                    docs.append(doc)

            browser.close()
        return docs

    def _discover_urls(self, page, source: dict) -> list[str]:
        start_url = source["url"]
        parsed_start = urlparse(start_url)

        # A direct post or Note is itself a valid source. A Note can additionally
        # act as a curated timeline containing links to many full articles.
        if parsed_start.path.startswith(("/p/", "/note/")) or "/note/" in parsed_start.path:
            urls = [self._canonical_url(start_url)]
            if source.get("follow_linked_articles", False):
                urls.extend(self._discover_linked_articles(page, start_url, source))
            return self._deduplicate(urls)

        return self._discover_publication_posts(page, start_url)

    def _discover_publication_posts(self, page, start_url: str) -> list[str]:
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
        urls: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = urljoin(start_url, anchor["href"])
            parsed = urlparse(href)
            if parsed.netloc == base_domain and parsed.path.startswith(("/p/", "/note/")):
                urls.append(self._canonical_url(href))
        return self._deduplicate(urls)

    def _discover_linked_articles(self, page, note_url: str, source: dict) -> list[str]:
        page.goto(note_url, wait_until="networkidle")
        page.wait_for_timeout(2000)
        soup = BeautifulSoup(page.content(), "html.parser")

        allowed_domains = set(source.get("allowed_domains", []))
        excluded_domains = {
            "substack.com",
            "www.substack.com",
            "twitter.com",
            "x.com",
        }
        urls: list[str] = []

        container = soup.find("article") or soup.find("main") or soup
        for anchor in container.find_all("a", href=True):
            href = self._canonical_url(urljoin(note_url, anchor["href"]))
            parsed = urlparse(href)
            if parsed.scheme not in {"http", "https"}:
                continue
            if parsed.netloc in excluded_domains:
                continue
            if allowed_domains and parsed.netloc not in allowed_domains:
                continue
            urls.append(href)

        return self._deduplicate(urls)

    def _extract_document(self, page, url: str, source: dict) -> KnowledgeDocument | None:
        try:
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(1500)
            soup = BeautifulSoup(page.content(), "html.parser")

            title_el = soup.find("h1") or soup.find("title")
            title = title_el.get_text(" ", strip=True) if title_el else url
            time_el = soup.find("time")
            published_date = time_el.get_text(" ", strip=True) if time_el else None
            author_el = soup.find(attrs={"rel": "author"}) or soup.find(
                class_=re.compile("author", re.I)
            )
            author = author_el.get_text(" ", strip=True) if author_el else None

            article_el = (
                soup.find("article")
                or soup.find("main")
                or soup.find("div", class_=re.compile("body|post|content", re.I))
            )
            if not article_el:
                return None

            content = md(str(article_el), heading_style="ATX").strip()
            links = [
                self._canonical_url(urljoin(url, anchor["href"]))
                for anchor in article_el.find_all("a", href=True)
            ]
            source_type = "substack-note" if "/note/" in urlparse(url).path else "substack"
            return KnowledgeDocument(
                title,
                url,
                source["name"],
                source_type,
                content,
                author,
                published_date,
                source.get("tags", []),
                self._deduplicate(links),
            )
        except Exception as exc:
            print(f"Failed Substack document {url}: {exc}")
            return None

    @staticmethod
    def _canonical_url(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

    @staticmethod
    def _deduplicate(urls: list[str]) -> list[str]:
        return list(dict.fromkeys(urls))

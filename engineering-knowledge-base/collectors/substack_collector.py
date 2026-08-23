from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from markdownify import markdownify as md
from playwright.sync_api import BrowserContext, Page, sync_playwright

from collectors.base import BaseCollector, KnowledgeDocument


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE_ROOT = ROOT / "output" / "raw" / "substack"


class SubstackCollector(BaseCollector):
    """
    Generic Substack collector.

    Supported modes:
      - article      : collect one /p/... article
      - publication  : discover articles from a publication page
      - saved        : discover articles from the authenticated Substack saved page

    Authentication:
      Preferred:
        user_data_dir: output/browser-profiles/substack

      Existing compatibility:
        storage_state_file: path/to/substack-state.json

    Archive:
      save_pdf: true
      save_html: true

    Incremental collection:
      collect.py passes skip_urls when --resume is used.
    """

    def __init__(self):
        self.last_report: dict = {}

    def collect(self, source: dict) -> list[KnowledgeDocument]:
        # Preserve the specialized existing course implementation.
        if source.get("course_mode"):
            from collectors.per_page_access_daily_course_collector import (
                PerPageAccessDailyCourseCollector,
            )

            collector = PerPageAccessDailyCourseCollector()
            documents = collector.collect(source)
            self.last_report = collector.last_report
            return documents

        mode = source.get("mode", "publication").strip().lower()
        delay_seconds = max(0, int(source.get("delay_seconds", 0)))
        min_content_chars = int(source.get("min_content_chars", 500))
        max_articles = source.get("max_articles")
        skip_urls = {
            self._canonicalize_url(url)
            for url in source.get("skip_urls", [])
        }

        self.last_report = {
            "source_name": source.get("name"),
            "mode": mode,
            "catalog_url": source.get("url"),
            "discovered": 0,
            "skipped_existing": 0,
            "attempted": 0,
            "deferred_by_limit": 0,
            "collected": 0,
            "failed": 0,
            "results": [],
        }

        docs: list[KnowledgeDocument] = []

        with sync_playwright() as playwright:
            context = self._create_context(playwright, source)

            try:
                page = context.new_page()

                urls = self._discover_urls(
                    page=page,
                    start_url=source["url"],
                    mode=mode,
                    source=source,
                )

                urls = self._deduplicate(urls)
                self.last_report["discovered"] = len(urls)

                pending_urls = []
                for url in urls:
                    canonical_url = self._canonicalize_url(url)
                    if canonical_url in skip_urls:
                        self.last_report["skipped_existing"] += 1
                        self.last_report["results"].append(
                            {
                                "url": canonical_url,
                                "status": "skipped_existing",
                                "content_chars": 0,
                            }
                        )
                        continue

                    pending_urls.append(canonical_url)

                if max_articles is not None:
                    max_articles = max(0, int(max_articles))
                    self.last_report["deferred_by_limit"] = max(
                        0,
                        len(pending_urls) - max_articles,
                    )
                    pending_urls = pending_urls[:max_articles]

                for index, url in enumerate(pending_urls):
                    self.last_report["attempted"] += 1

                    doc = self._extract_post(
                        page=page,
                        url=url,
                        source=source,
                    )

                    if doc and len(doc.content.strip()) >= min_content_chars:
                        docs.append(doc)
                        self.last_report["collected"] += 1
                        self.last_report["results"].append(
                            {
                                "url": url,
                                "title": doc.title,
                                "status": "collected",
                                "content_chars": len(doc.content),
                            }
                        )
                    else:
                        self.last_report["failed"] += 1
                        self.last_report["results"].append(
                            {
                                "url": url,
                                "title": doc.title if doc else None,
                                "status": "failed_or_too_short",
                                "content_chars": len(doc.content) if doc else 0,
                            }
                        )

                    # Delay only BETWEEN article collections.
                    if index < len(pending_urls) - 1 and delay_seconds > 0:
                        print(
                            f"Substack delay: waiting {delay_seconds} seconds "
                            f"before next article..."
                        )
                        time.sleep(delay_seconds)

                storage_state_file = source.get("storage_state_file")
                if storage_state_file and not source.get("user_data_dir"):
                    state_path = Path(storage_state_file)
                    state_path.parent.mkdir(parents=True, exist_ok=True)
                    context.storage_state(path=str(state_path))

            finally:
                context.close()

        return docs

    def _create_context(self, playwright, source: dict) -> BrowserContext:
        headless = bool(source.get("headless", False))
        user_data_dir = source.get("user_data_dir")

        if user_data_dir:
            profile_path = Path(user_data_dir)
            if not profile_path.is_absolute():
                profile_path = ROOT / profile_path

            profile_path.mkdir(parents=True, exist_ok=True)

            return playwright.chromium.launch_persistent_context(
                user_data_dir=str(profile_path),
                headless=headless,
                viewport={"width": 1440, "height": 1000},
            )

        browser = playwright.chromium.launch(headless=headless)

        storage_state_file = source.get("storage_state_file")

        if storage_state_file:
            state_path = Path(storage_state_file)

            if not state_path.is_absolute():
                state_path = ROOT / state_path

            if state_path.exists():
                return browser.new_context(
                    storage_state=str(state_path),
                    viewport={"width": 1440, "height": 1000},
                )

        return browser.new_context(
            viewport={"width": 1440, "height": 1000},
        )

    def _discover_urls(
        self,
        page: Page,
        start_url: str,
        mode: str,
        source: dict,
    ) -> list[str]:
        canonical_start = self._canonicalize_url(start_url)

        # A direct article URL does not need discovery.
        if mode == "article" or "/p/" in urlparse(canonical_start).path:
            return [canonical_start]

        print(f"Opening Substack source: {start_url}")

        page.goto(
            start_url,
            wait_until="domcontentloaded",
            timeout=90_000,
        )
        page.wait_for_timeout(2500)

        if mode == "saved":
            self._wait_for_authenticated_saved_page(page, source)

        # Try common expandable controls.
        for label in ("See all", "Load more", "More"):
            try:
                locator = page.get_by_text(label, exact=True)

                if locator.count() > 0 and locator.first.is_visible():
                    locator.first.click()
                    page.wait_for_timeout(1500)
            except Exception:
                pass

        self._scroll_to_end(
            page,
            max_scrolls=int(source.get("max_scrolls", 50)),
        )

        soup = BeautifulSoup(page.content(), "html.parser")

        if mode == "saved":
            return self._discover_saved_article_links(
                soup=soup,
                page_url=page.url,
            )

        return self._discover_publication_links(
            soup=soup,
            start_url=start_url,
        )

    def _wait_for_authenticated_saved_page(
        self,
        page: Page,
        source: dict,
    ) -> None:
        """
        First run can be headed.

        If Substack redirects to sign-in, the user can authenticate manually.
        The persistent user_data_dir retains that session for later runs.
        """

        current = page.url.lower()

        looks_like_login = any(
            marker in current
            for marker in (
                "/sign-in",
                "/signin",
                "/login",
            )
        )

        if not looks_like_login:
            return

        if bool(source.get("headless", False)):
            raise RuntimeError(
                "Substack authentication is required. "
                "Run once with headless: false using a persistent user_data_dir."
            )

        login_wait_seconds = int(
            source.get("login_wait_seconds", 180)
        )

        print(
            "Substack login required. Complete login in the opened browser. "
            f"Waiting up to {login_wait_seconds} seconds..."
        )

        deadline = time.time() + login_wait_seconds

        while time.time() < deadline:
            page.wait_for_timeout(2000)

            current = page.url.lower()

            if not any(
                marker in current
                for marker in (
                    "/sign-in",
                    "/signin",
                    "/login",
                )
            ):
                page.wait_for_timeout(2000)
                return

        raise RuntimeError(
            "Substack login was not completed before timeout."
        )

    def _discover_publication_links(
        self,
        soup: BeautifulSoup,
        start_url: str,
    ) -> list[str]:
        base_domain = urlparse(start_url).netloc.lower()

        urls: list[str] = []

        for anchor in soup.find_all("a", href=True):
            href = urljoin(start_url, anchor["href"])
            parsed = urlparse(href)

            if parsed.netloc.lower() != base_domain:
                continue

            if not parsed.path.startswith("/p/"):
                continue

            urls.append(self._canonicalize_url(href))

        return urls

    def _discover_saved_article_links(
        self,
        soup: BeautifulSoup,
        page_url: str,
    ) -> list[str]:
        """
        Saved articles can belong to different Substack publications,
        including publications using custom domains.

        Therefore saved-mode discovery must NOT restrict links to the
        current substack.com hostname.
        """

        urls: list[str] = []

        for anchor in soup.find_all("a", href=True):
            href = urljoin(page_url, anchor["href"])
            parsed = urlparse(href)

            if parsed.scheme not in ("http", "https"):
                continue

            if "/p/" not in parsed.path:
                continue

            urls.append(self._canonicalize_url(href))

        return urls

    def _extract_post(
        self,
        page: Page,
        url: str,
        source: dict,
    ) -> KnowledgeDocument | None:
        try:
            print(f"Collecting Substack article: {url}")

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=90_000,
            )

            page.wait_for_timeout(
                int(source.get("article_wait_ms", 2000))
            )

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            title_el = soup.find("h1")

            title = (
                title_el.get_text(" ", strip=True)
                if title_el
                else url
            )

            time_el = soup.find("time")
            published_date = (
                time_el.get("datetime")
                or time_el.get_text(" ", strip=True)
                if time_el
                else None
            )

            author = self._extract_author(soup)

            article_el = (
                soup.find("article")
                or soup.find(
                    "div",
                    class_=re.compile(
                        r"(available-content|body|post)",
                        re.I,
                    ),
                )
            )

            if not article_el:
                print(f"No article body found: {url}")
                return None

            content = md(
                str(article_el),
                heading_style="ATX",
            ).strip()

            links = self._deduplicate(
                [
                    self._canonicalize_url(
                        urljoin(url, anchor["href"])
                    )
                    for anchor in article_el.find_all(
                        "a",
                        href=True,
                    )
                ]
            )

            archive_metadata = self._archive_article(
                page=page,
                html=html,
                title=title,
                url=url,
                source=source,
            )

            return KnowledgeDocument(
                title=title,
                url=self._canonicalize_url(url),
                source_name=source["name"],
                source_type="substack",
                content=content,
                author=author,
                published_date=published_date,
                tags=source.get("tags", []),
                links=links,
                metadata={
                    "collection_mode": source.get(
                        "mode",
                        "publication",
                    ),
                    **archive_metadata,
                },
            )

        except Exception as exc:
            print(f"Failed Substack post {url}: {exc}")
            return None

    def _archive_article(
        self,
        page: Page,
        html: str,
        title: str,
        url: str,
        source: dict,
    ) -> dict:
        save_pdf = bool(source.get("save_pdf", False))
        save_html = bool(source.get("save_html", False))

        if not save_pdf and not save_html:
            return {}

        archive_root = source.get("archive_dir")

        if archive_root:
            archive_root = Path(archive_root)

            if not archive_root.is_absolute():
                archive_root = ROOT / archive_root
        else:
            archive_root = (
                DEFAULT_ARCHIVE_ROOT
                / self._safe_name(source["name"])
            )

        article_key = self._safe_name(title)[:80]
        url_hash = self._short_hash(url)
        stem = f"{article_key}-{url_hash}"

        archive_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        metadata: dict = {}

        if save_html:
            html_dir = archive_root / "html"
            html_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            html_path = html_dir / f"{stem}.html"
            html_path.write_text(
                html,
                encoding="utf-8",
            )

            metadata["archive_html"] = str(
                html_path.relative_to(ROOT)
            )

        if save_pdf:
            pdf_dir = archive_root / "pdf"
            pdf_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            pdf_path = pdf_dir / f"{stem}.pdf"

            page.emulate_media(media="print")

            page.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
                margin={
                    "top": "15mm",
                    "right": "12mm",
                    "bottom": "15mm",
                    "left": "12mm",
                },
            )

            metadata["archive_pdf"] = str(
                pdf_path.relative_to(ROOT)
            )

        return metadata

    @staticmethod
    def _extract_author(
        soup: BeautifulSoup,
    ) -> str | None:
        meta_author = soup.find(
            "meta",
            attrs={"name": "author"},
        )

        if meta_author and meta_author.get("content"):
            return meta_author["content"].strip()

        return None

    @staticmethod
    def _scroll_to_end(
        page: Page,
        max_scrolls: int,
    ) -> None:
        previous_height = -1
        stable_iterations = 0

        for _ in range(max_scrolls):
            page.mouse.wheel(0, 3500)
            page.wait_for_timeout(800)

            height = page.evaluate(
                "document.body.scrollHeight"
            )

            if height == previous_height:
                stable_iterations += 1

                if stable_iterations >= 3:
                    break
            else:
                stable_iterations = 0

            previous_height = height

    @staticmethod
    def _canonicalize_url(url: str) -> str:
        parsed = urlparse(url)

        return urlunparse(
            (
                parsed.scheme or "https",
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                "",
                "",
                "",
            )
        )

    @staticmethod
    def _deduplicate(values: list[str]) -> list[str]:
        seen = set()
        result = []

        for value in values:
            if not value or value in seen:
                continue

            seen.add(value)
            result.append(value)

        return result

    @staticmethod
    def _safe_name(value: str) -> str:
        cleaned = re.sub(
            r"[^A-Za-z0-9._-]+",
            "-",
            value.strip(),
        )

        return cleaned.strip("-") or "article"

    @staticmethod
    def _short_hash(value: str) -> str:
        import hashlib

        return hashlib.sha256(
            value.encode("utf-8")
        ).hexdigest()[:12]
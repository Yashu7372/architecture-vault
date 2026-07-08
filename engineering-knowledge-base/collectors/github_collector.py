from urllib.parse import urlparse
import requests

from collectors.base import BaseCollector, KnowledgeDocument


class GitHubCollector(BaseCollector):
    def collect(self, source: dict) -> list[KnowledgeDocument]:
        owner, repo = self._parse_repo(source["url"])
        repo_info = self._get_json(f"https://api.github.com/repos/{owner}/{repo}") or {}

        docs: list[KnowledgeDocument] = []

        readme = self._fetch_raw(owner, repo, "README.md")
        if readme:
            docs.append(
                KnowledgeDocument(
                    title=f"{owner}/{repo} README",
                    url=source["url"],
                    source_name=source["name"],
                    source_type="github",
                    content=readme,
                    author=owner,
                    published_date=repo_info.get("updated_at"),
                    tags=source.get("tags", []),
                    links=[source["url"]],
                )
            )

        for path in self._find_important_markdown(owner, repo)[:30]:
            content = self._fetch_raw(owner, repo, path)
            if content and len(content) > 500:
                docs.append(
                    KnowledgeDocument(
                        title=f"{owner}/{repo} - {path}",
                        url=f"{source['url']}/blob/main/{path}",
                        source_name=source["name"],
                        source_type="github",
                        content=content,
                        author=owner,
                        published_date=repo_info.get("updated_at"),
                        tags=source.get("tags", []),
                        links=[source["url"]],
                    )
                )

        return docs

    def _parse_repo(self, url: str) -> tuple[str, str]:
        parts = urlparse(url).path.strip("/").split("/")
        if len(parts) < 2:
            raise ValueError(f"Invalid GitHub repo URL: {url}")
        return parts[0], parts[1]

    def _get_json(self, url: str) -> dict | None:
        response = requests.get(url, headers={"User-Agent": "engineering-knowledge-collector"}, timeout=30)
        return response.json() if response.ok else None

    def _fetch_raw(self, owner: str, repo: str, path: str) -> str | None:
        for branch in ["main", "master"]:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
            response = requests.get(url, headers={"User-Agent": "engineering-knowledge-collector"}, timeout=30)
            if response.ok:
                return response.text
        return None

    def _find_important_markdown(self, owner: str, repo: str) -> list[str]:
        url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
        data = self._get_json(url) or {}
        tree = data.get("tree", [])
        keywords = ["architecture", "design", "docs", "agent", "rag", "memory", "workflow", "examples", "system"]
        results = []
        for item in tree:
            path = item.get("path", "")
            lower = path.lower()
            if lower.endswith(".md") and any(k in lower for k in keywords):
                results.append(path)
        return results

from pathlib import Path
from urllib.parse import urlparse
import re
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "input" / "chrome-bookmarks.html"
OUTPUT_FILE = ROOT / "config" / "sources.generated.yaml"


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:80]


def detect_source_type(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    if "substack.com" in domain:
        return "substack"
    if "github.com" in domain:
        return "github"
    if "youtube.com" in domain or "youtu.be" in domain:
        return "youtube"
    if url.lower().endswith(".pdf"):
        return "pdf"
    return "web"


def detect_tags(title: str, url: str) -> list[str]:
    text = f"{title} {url}".lower()
    mapping = {
        "ai-agents": ["agent", "agents", "multi-agent", "workflow"],
        "rag": ["rag", "retrieval", "embedding", "vector"],
        "llm": ["llm", "gpt", "claude", "gemini", "language-model"],
        "distributed-systems": ["distributed", "scale", "scaling", "storage"],
        "event-driven": ["event", "kafka", "pubsub", "queue", "stream"],
        "database": ["database", "sql", "postgres", "oracle", "query"],
        "observability": ["observability", "monitoring", "metrics", "tracing", "logs"],
        "payments": ["payment", "payments", "ledger", "settlement"],
        "platform-engineering": ["platform", "infrastructure", "devops"],
        "system-design": ["architecture", "system-design", "design"],
    }
    tags = [tag for tag, keywords in mapping.items() if any(keyword in text for keyword in keywords)]
    return tags or ["to-classify"]


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Place Chrome export at: {INPUT_FILE}")
    soup = BeautifulSoup(INPUT_FILE.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    sources = []
    seen = set()
    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True) or "untitled"
        url = a["href"].strip()
        if not url.startswith("http") or url in seen:
            continue
        seen.add(url)
        source_type = detect_source_type(url)
        item = {"name": slugify(title), "type": source_type, "url": url, "tags": detect_tags(title, url)}
        if source_type == "substack":
            item["login_required"] = True
            item["auth_profile"] = "substack"
        sources.append(item)
    OUTPUT_FILE.write_text(yaml.dump({"sources": sources}, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Imported {len(sources)} bookmarks to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()

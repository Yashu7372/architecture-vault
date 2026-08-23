from pathlib import Path
from urllib.parse import urlparse


def detect_source_type(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()

    if "github.com" in host:
        return "github"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "arxiv.org" in host:
        return "arxiv"
    if "substack.com" in host:
        return "substack"
    if path.endswith(".pdf"):
        return "pdf"
    return "web"


def build_source(url: str) -> dict:
    parsed = urlparse(url)
    source_type = detect_source_type(url)
    name = parsed.netloc or Path(parsed.path).stem or source_type
    source = {
        "name": name,
        "type": source_type,
        "url": url,
        "tags": [source_type, "inbox"],
    }
    if source_type in {"web", "substack"}:
        source["mode"] = "exact"
    return source

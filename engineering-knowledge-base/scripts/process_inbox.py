from __future__ import annotations

from pathlib import Path
import argparse
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collectors.arxiv_collector import ArxivCollector
from collectors.github_collector import GitHubCollector
from collectors.pdf_collector import PdfCollector
from collectors.substack_collector import SubstackCollector
from collectors.web_collector import WebCollector
from collectors.youtube_collector import YouTubeCollector
from processors.artifact_writer import ArtifactWriter
from processors.source_router import build_source
from processors.state_store import StateStore

INBOX_FILE = ROOT / "inbox" / "inbox.md"
STATE_FILE = ROOT / "output" / "state" / "inbox-state.json"
URL_RE = re.compile(r"https?://[^\s)>\]]+")


def get_collector(source_type: str):
    collectors = {
        "web": WebCollector(),
        "substack": SubstackCollector(),
        "github": GitHubCollector(),
        "arxiv": ArxivCollector(),
        "pdf": PdfCollector(),
        "youtube": YouTubeCollector(),
    }
    try:
        return collectors[source_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported source type: {source_type}") from exc


def read_inbox(path: Path) -> list[str]:
    if not path.exists():
        return []
    urls = []
    seen = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = URL_RE.search(line)
        if not match:
            continue
        url = match.group(0).rstrip(".,;")
        if url not in seen and "example.com/replace-with-an-article" not in url:
            seen.add(url)
            urls.append(url)
    return urls


def process_url(url: str, state: StateStore, writer: ArtifactWriter, retry_failed: bool) -> str:
    source = build_source(url)
    source_id = writer.source_id(url)
    if not state.should_process(source_id, retry_failed=retry_failed):
        return "SKIPPED"

    state.mark(source_id, url, "PROCESSING", source_type=source["type"])
    try:
        docs = get_collector(source["type"]).collect(source)
        if not docs:
            raise RuntimeError("collector returned no usable content")

        artifacts = []
        for doc in docs:
            raw_path = writer.write_raw(doc)
            packet_path = writer.write_analysis_packet(doc, raw_path)
            artifacts.append({
                "raw": str(raw_path.relative_to(ROOT)),
                "analysis_packet": str(packet_path.relative_to(ROOT)),
            })

        state.mark(
            source_id,
            url,
            "READY_FOR_AI_ANALYSIS",
            source_type=source["type"],
            artifacts=artifacts,
            error=None,
        )
        return "READY_FOR_AI_ANALYSIS"
    except Exception as exc:
        state.mark(source_id, url, "FAILED", source_type=source["type"], error=str(exc))
        return "FAILED"


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract exact links from inbox.md into raw evidence and AI analysis packets.")
    parser.add_argument("--inbox", type=Path, default=INBOX_FILE)
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()

    urls = read_inbox(args.inbox)
    state = StateStore(STATE_FILE)
    writer = ArtifactWriter(ROOT)

    totals = {"READY_FOR_AI_ANALYSIS": 0, "FAILED": 0, "SKIPPED": 0}
    for index, url in enumerate(urls, start=1):
        result = process_url(url, state, writer, args.retry_failed)
        totals[result] = totals.get(result, 0) + 1
        print(f"[{index}/{len(urls)}] {result}: {url}")

    print(
        "Done. "
        f"ready={totals.get('READY_FOR_AI_ANALYSIS', 0)} "
        f"failed={totals.get('FAILED', 0)} "
        f"skipped={totals.get('SKIPPED', 0)}"
    )


if __name__ == "__main__":
    main()

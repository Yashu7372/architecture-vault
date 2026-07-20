from __future__ import annotations

from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from time import perf_counter
import json
import sys

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collectors.catalog_collector import CatalogCollector, CatalogEntry
from collectors.web_collector import DEFAULT_HEADERS
from settings import OUTPUT_DIR

CONFIG_FILES = [ROOT / "config" / "sources.manual.yaml", ROOT / "config" / "sources.generated.yaml"]
REPORT_DIR = OUTPUT_DIR / "reports"


def load_catalog_source(name: str) -> dict:
    for config_file in CONFIG_FILES:
        if not config_file.exists():
            continue
        data = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        for source in data.get("sources", []):
            if source.get("name") == name:
                if source.get("type") != "catalog":
                    raise ValueError(f"Source {name} is type {source.get('type')}, not catalog")
                return source
    raise ValueError(f"Catalog source not found: {name}")


def check_entry(entry: CatalogEntry, timeout: int) -> dict:
    started = perf_counter()
    try:
        response = requests.get(
            entry.url,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        )
        result = {
            "title": entry.title,
            "url": entry.url,
            "final_url": response.url,
            "status_code": response.status_code,
            "ok": 200 <= response.status_code < 400,
            "content_type": response.headers.get("content-type", ""),
            "elapsed_ms": round((perf_counter() - started) * 1000),
            "locations": [
                {"section": section, "subsection": subsection}
                for section, subsection in entry.locations
            ],
        }
        response.close()
        return result
    except Exception as exc:
        return {
            "title": entry.title,
            "url": entry.url,
            "final_url": None,
            "status_code": None,
            "ok": False,
            "content_type": None,
            "elapsed_ms": round((perf_counter() - started) * 1000),
            "error": str(exc),
            "locations": [
                {"section": section, "subsection": subsection}
                for section, subsection in entry.locations
            ],
        }


def write_markdown_report(source_name: str, results: list[dict], path: Path) -> None:
    failures = [result for result in results if not result["ok"]]
    redirects = [
        result for result in results if result.get("final_url") and result["final_url"] != result["url"]
    ]
    lines = [
        f"# Catalog Validation: {source_name}",
        "",
        f"- Unique article links: {len(results)}",
        f"- Reachable: {len(results) - len(failures)}",
        f"- Failed: {len(failures)}",
        f"- Redirected: {len(redirects)}",
        "",
        "## Failures",
        "",
    ]
    if failures:
        lines.extend(
            f"- `{item.get('status_code') or 'ERROR'}` [{item['title']}]({item['url']})"
            + (f" — {item['error']}" if item.get("error") else "")
            for item in failures
        )
    else:
        lines.append("No failures detected.")

    lines.extend(["", "## Redirects", ""])
    if redirects:
        lines.extend(
            f"- [{item['title']}]({item['url']}) → {item['final_url']}" for item in redirects
        )
    else:
        lines.append("No redirects detected.")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = ArgumentParser(description="Validate every unique article link in a Markdown catalog source.")
    parser.add_argument("--source", default="system-design-academy")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args()

    source = load_catalog_source(args.source)
    entries = CatalogCollector().discover_entries(source)
    print(f"Discovered {len(entries)} unique article links in {args.source}")

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(check_entry, entry, args.timeout): entry for entry in entries}
        for completed, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            results.append(result)
            state = "OK" if result["ok"] else "FAILED"
            print(f"[{completed}/{len(entries)}] {state}: {result['title']}")

    order = {entry.url: entry.order for entry in entries}
    results.sort(key=lambda item: order[item["url"]])
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORT_DIR / f"{args.source}-validation.json"
    markdown_path = REPORT_DIR / f"{args.source}-validation.md"
    payload = {
        "source": args.source,
        "catalog_url": source.get("catalog_page", source["url"]),
        "total": len(results),
        "reachable": sum(1 for result in results if result["ok"]),
        "failed": sum(1 for result in results if not result["ok"]),
        "results": results,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown_report(args.source, results, markdown_path)
    print(f"Validation reports: {json_path} and {markdown_path}")

    if args.fail_on_error and payload["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

from __future__ import annotations

from argparse import ArgumentParser
from collections import Counter
from pathlib import Path
import json

from slugify import slugify

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"
COURSES_DIR = OUTPUT_DIR / "courses"


def parse_args():
    parser = ArgumentParser(description="Build an ordered learning path from collected course lesson notes.")
    parser.add_argument("--source", action="append", required=True, help="Course source name. Repeat as needed.")
    return parser.parse_args()


def build_course_guide(source_name: str, items: list[dict]) -> Path:
    items.sort(key=lambda item: item.get("metadata", {}).get("curriculum_order", 10**9))
    folder = COURSES_DIR / slugify(source_name)
    folder.mkdir(parents=True, exist_ok=True)
    output_file = folder / "LEARNING_PATH.md"

    access_counts = Counter(item.get("metadata", {}).get("access_level", "unknown") for item in items)
    lines = [
        f"# Learning Path: {source_name}",
        "",
        "> This guide indexes public curriculum records, publicly visible article text, and original stitched study guides. "
        "It does not include or reconstruct subscriber-only content.",
        "",
        f"- Lessons collected: {len(items)}",
        f"- Public articles: {access_counts.get('public', 0)}",
        f"- Public previews: {access_counts.get('preview', 0)}",
        f"- Curriculum-only lessons: {access_counts.get('curriculum-only', 0)}",
        "",
    ]

    current_module = None
    current_week = None
    for item in items:
        metadata = item.get("metadata", {})
        module = metadata.get("course_module", "Uncategorized Module")
        week = metadata.get("course_week", "Uncategorized Week")
        if module != current_module:
            current_module = module
            current_week = None
            lines.extend([f"## {module}", ""])
        if week != current_week:
            current_week = week
            lines.extend([f"### {week}", ""])

        day = metadata.get("curriculum_day", "?")
        access = metadata.get("access_level", "unknown")
        expected_output = metadata.get("expected_output", "")
        article_url = metadata.get("article_url")
        note_file = item["note_file"]
        lines.append(f"#### Day {day}: {item['title'].split(':', 1)[-1].strip()}")
        lines.append("")
        lines.append(f"- Access: `{access}`")
        lines.append(f"- [Stitched lesson note](../../{note_file})")
        if article_url:
            lines.append(f"- [Original article]({article_url})")
        if expected_output:
            lines.append(f"- Expected output: {expected_output}")
        lines.append("")

    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def main():
    args = parse_args()
    if not MANIFEST_FILE.exists():
        raise FileNotFoundError(f"Run scripts/collect.py first; missing {MANIFEST_FILE}")

    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    for source_name in args.source:
        items = [item for item in manifest if item.get("source_name") == source_name]
        if not items:
            print(f"No collected lessons found for source: {source_name}")
            continue
        output_file = build_course_guide(source_name, items)
        print(f"Course guide: {output_file}")


if __name__ == "__main__":
    main()

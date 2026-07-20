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
REPORT_DIR = OUTPUT_DIR / "reports"


def parse_args():
    parser = ArgumentParser(description="Build ordered learning and curriculum guides from course output.")
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
        "> This guide indexes public curriculum records, publicly visible article text, and original study guides. "
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
        lines.append(f"- [Collected lesson note](../../{note_file})")
        if article_url:
            lines.append(f"- [Original article]({article_url})")
        if expected_output:
            lines.append(f"- Expected output: {expected_output}")
        lines.append("")

    output_file.write_text("\n".join(lines), encoding="utf-8")
    return output_file


def load_collection_report(source_name: str) -> dict:
    path = REPORT_DIR / f"{slugify(source_name)}-collection.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_curriculum_context(source_name: str, report: dict) -> tuple[Path, Path] | None:
    curriculum = report.get("curriculum", [])
    if not curriculum:
        return None

    folder = COURSES_DIR / slugify(source_name)
    folder.mkdir(parents=True, exist_ok=True)
    json_file = folder / "CURRICULUM_CONTEXT.json"
    markdown_file = folder / "CURRICULUM_CONTEXT.md"
    json_file.write_text(json.dumps(curriculum, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        f"# Complete Curriculum Context: {source_name}",
        "",
        "> This file contains public curriculum metadata only: module, week, day, title, expected output, and article link. "
        "It does not contain subscriber-only lesson bodies.",
        "",
        f"- Curriculum URL: {report.get('catalog_url', '')}",
        f"- Lessons discovered: {len(curriculum)}",
        "",
    ]
    current_module = None
    current_week = None
    for lesson in sorted(curriculum, key=lambda item: item.get("order", 10**9)):
        module = lesson.get("module") or "Uncategorized Module"
        week = lesson.get("week") or "Uncategorized Week"
        if module != current_module:
            current_module = module
            current_week = None
            lines.extend([f"## {module}", ""])
        if week != current_week:
            current_week = week
            lines.extend([f"### {week}", ""])
        day = lesson.get("day", "?")
        title = lesson.get("title", "Untitled lesson")
        article_url = lesson.get("article_url")
        expected_output = lesson.get("expected_output")
        heading = f"#### Day {day}: {title}"
        lines.extend([heading, ""])
        if article_url:
            lines.append(f"- Article: {article_url}")
        if expected_output:
            lines.append(f"- Expected output: {expected_output}")
        lines.append("")

    markdown_file.write_text("\n".join(lines), encoding="utf-8")
    return markdown_file, json_file


def main():
    args = parse_args()
    if not MANIFEST_FILE.exists():
        raise FileNotFoundError(f"Run scripts/collect.py first; missing {MANIFEST_FILE}")

    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    for source_name in args.source:
        items = [item for item in manifest if item.get("source_name") == source_name]
        if items:
            output_file = build_course_guide(source_name, items)
            print(f"Course guide: {output_file}")
        else:
            print(f"No collected lessons found for source: {source_name}")

        curriculum_files = build_curriculum_context(source_name, load_collection_report(source_name))
        if curriculum_files:
            print(f"Curriculum context: {curriculum_files[0]} and {curriculum_files[1]}")


if __name__ == "__main__":
    main()

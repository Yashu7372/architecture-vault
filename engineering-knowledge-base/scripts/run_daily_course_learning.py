from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
import json
import os
import subprocess
import sys
import time

from slugify import slugify

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
OUTPUT_DIR = ROOT / "output"
MANIFEST_FILE = OUTPUT_DIR / "manifest.json"
DAILY_DIR = OUTPUT_DIR / "daily-learning"
SCHEDULER_DIR = OUTPUT_DIR / "scheduler"
STATE_FILE = SCHEDULER_DIR / "sdcourse-state.json"
LOCK_FILE = SCHEDULER_DIR / "sdcourse.lock"
REPORT_DIR = OUTPUT_DIR / "reports"

TRACK_SOURCES = {
    "python-js": "sdcourse-python-js",
    "java-spring": "sdcourse-java-spring",
}


class SchedulerLock:
    def __enter__(self):
        SCHEDULER_DIR.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise RuntimeError(f"Another SDCourse scheduler run is active: {LOCK_FILE}") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"pid": os.getpid(), "started_at": now_iso()}))
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        LOCK_FILE.unlink(missing_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def load_manifest() -> list[dict]:
    return load_json(MANIFEST_FILE, [])


def source_items(manifest: Iterable[dict], source_name: str) -> list[dict]:
    items = [item for item in manifest if item.get("source_name") == source_name]
    return sorted(items, key=lambda item: item.get("metadata", {}).get("curriculum_order", 10**9))


def run_script(script: str, *arguments: str) -> None:
    command = [sys.executable, str(SCRIPTS_DIR / script), *arguments]
    print(f"\n> {' '.join(command)}")
    subprocess.run(command, check=True, cwd=ROOT.parent)


def extracted_document_body(note_text: str) -> str:
    extracted_marker = "## Extracted Content"
    notes_marker = "## My Architecture Notes"
    if extracted_marker not in note_text:
        return note_text.strip()
    body = note_text.split(extracted_marker, 1)[1]
    if notes_marker in body:
        body = body.split(notes_marker, 1)[0]
    return body.strip("\n -")


def split_lesson_content(note_text: str) -> tuple[str, str]:
    body = extracted_document_body(note_text)
    marker = "## Part 2 — Original Completed Lesson"
    if marker not in body:
        raise ValueError("Collected lesson does not contain the original completed-lesson section")
    public_capture, completed = body.split(marker, 1)
    public_capture = public_capture.strip()
    completed = f"{marker}\n\n{completed.strip()}"
    return public_capture, completed


def lesson_header(item: dict, artifact_kind: str) -> str:
    metadata = item.get("metadata", {})
    article_url = metadata.get("article_url") or metadata.get("curriculum_url") or item.get("url", "")
    return f"""# {item['title']} — {artifact_kind}

- Course: {item.get('source_name', '')}
- Track: {metadata.get('course_track', '')}
- Curriculum day: {metadata.get('curriculum_day', '')}
- Module: {metadata.get('course_module', '')}
- Week: {metadata.get('course_week', '')}
- Public access: {metadata.get('access_level', '')}
- Completion mode: {metadata.get('lesson_completion_mode', '')}
- Source: {article_url}

"""


def write_daily_artifacts(item: dict) -> dict:
    metadata = item.get("metadata", {})
    day = int(metadata["curriculum_day"])
    note_path = OUTPUT_DIR / item["note_file"]
    if not note_path.exists():
        raise FileNotFoundError(f"Collected note is missing: {note_path}")
    public_capture, completed_lesson = split_lesson_content(note_path.read_text(encoding="utf-8"))

    folder = DAILY_DIR / slugify(item["source_name"]) / f"day-{day:03d}"
    folder.mkdir(parents=True, exist_ok=True)
    source_file = folder / "01-public-source.md"
    lesson_file = folder / "02-completed-lesson.md"
    status_file = folder / "STATUS.json"

    source_file.write_text(
        lesson_header(item, "Public Source Capture")
        + "> This file contains only curriculum metadata and material visible without subscriber access.\n\n"
        + public_capture
        + "\n",
        encoding="utf-8",
    )
    lesson_file.write_text(
        lesson_header(item, "Original Completed Lesson")
        + "> This is original educational material. It is not a reconstruction of subscriber-only course text.\n\n"
        + completed_lesson
        + "\n",
        encoding="utf-8",
    )
    status = {
        "source_name": item["source_name"],
        "day": day,
        "title": item["title"],
        "access_level": metadata.get("access_level"),
        "public_content_chars": metadata.get("public_content_chars", 0),
        "completion_mode": metadata.get("lesson_completion_mode"),
        "completion_model": metadata.get("lesson_completion_model"),
        "completion_error": metadata.get("lesson_completion_error"),
        "source_file": str(source_file.relative_to(OUTPUT_DIR)),
        "lesson_file": str(lesson_file.relative_to(OUTPUT_DIR)),
        "generated_at": now_iso(),
    }
    write_json(status_file, status)
    return status


def report_for_source(source_name: str) -> dict:
    report_file = REPORT_DIR / f"{slugify(source_name)}-collection.json"
    return load_json(report_file, {})


def update_scheduler_state(state: dict, source_name: str, items: list[dict], generated: list[dict]) -> None:
    track_state = state.setdefault("tracks", {}).setdefault(source_name, {})
    days = sorted(int(item.get("metadata", {}).get("curriculum_day", 0)) for item in items)
    report = report_for_source(source_name)
    discovered = int(report.get("discovered", max(days, default=0)))
    completed_days = [day for day in days if day > 0]
    pending_days = [day for day in range(1, discovered + 1) if day not in set(completed_days)]
    track_state.update(
        {
            "last_run_at": now_iso(),
            "discovered_lessons": discovered,
            "completed_lessons": len(completed_days),
            "completed_days": completed_days,
            "last_completed_day": max(completed_days, default=None),
            "next_pending_day": pending_days[0] if pending_days else None,
            "remaining_lessons": len(pending_days),
            "last_generated": generated,
            "last_collection_report": report,
        }
    )
    state["updated_at"] = now_iso()
    state["version"] = 1


def run_once(
    *,
    tracks: list[str],
    lessons_per_run: int,
    rebuild_context: bool,
) -> dict:
    source_names = [TRACK_SOURCES[track] for track in tracks]
    before_manifest = load_manifest()
    before_ids = {
        source_name: {item["document_id"] for item in source_items(before_manifest, source_name)}
        for source_name in source_names
    }

    collection_args: list[str] = []
    for source_name in source_names:
        collection_args.extend(["--source", source_name])
    collection_args.extend(["--resume", "--max-articles", str(lessons_per_run)])
    run_script("collect.py", *collection_args)

    after_manifest = load_manifest()
    state = load_json(STATE_FILE, {"version": 1, "tracks": {}})
    summary = {"started_at": now_iso(), "tracks": {}}
    for source_name in source_names:
        items = source_items(after_manifest, source_name)
        new_items = [item for item in items if item["document_id"] not in before_ids[source_name]]
        generated = []
        for item in new_items:
            generated.append(write_daily_artifacts(item))
        update_scheduler_state(state, source_name, items, generated)
        summary["tracks"][source_name] = {
            "new_lessons": len(new_items),
            "generated": generated,
            "next_pending_day": state["tracks"][source_name].get("next_pending_day"),
            "remaining_lessons": state["tracks"][source_name].get("remaining_lessons"),
        }

    guide_args: list[str] = []
    for source_name in source_names:
        guide_args.extend(["--source", source_name])
    run_script("build_course_guide.py", *guide_args)
    run_script("build_index.py")
    if rebuild_context:
        run_script("build_context.py")

    summary["completed_at"] = now_iso()
    state["last_run"] = summary
    write_json(STATE_FILE, state)
    print(f"\nScheduler state: {STATE_FILE}")
    return summary


def parse_args():
    parser = ArgumentParser(
        description=(
            "Collect the next SDCourse lesson(s), save the public source separately, and generate a complete original lesson."
        )
    )
    parser.add_argument("--track", choices=["python-js", "java-spring", "all"], default="python-js")
    parser.add_argument("--lessons-per-run", type=int, default=1)
    parser.add_argument("--daemon", action="store_true", help="Repeat forever using --interval-hours.")
    parser.add_argument("--interval-hours", type=float, default=24.0)
    parser.add_argument("--rebuild-context", action="store_true", help="Also rebuild SQLite/FTS retrieval artifacts.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.lessons_per_run < 1:
        raise ValueError("--lessons-per-run must be at least 1")
    if args.interval_hours <= 0:
        raise ValueError("--interval-hours must be positive")
    tracks = list(TRACK_SOURCES) if args.track == "all" else [args.track]

    while True:
        with SchedulerLock():
            run_once(
                tracks=tracks,
                lessons_per_run=args.lessons_per_run,
                rebuild_context=args.rebuild_context,
            )
        if not args.daemon:
            break
        sleep_seconds = args.interval_hours * 60 * 60
        print(f"\nNext run in {args.interval_hours:g} hour(s).")
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    main()

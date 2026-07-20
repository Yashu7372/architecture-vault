from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"

TRACK_SOURCES = {
    "python-js": "sdcourse-python-js",
    "java-spring": "sdcourse-java-spring",
}


def run(script: str, *arguments: str) -> None:
    command = [sys.executable, str(SCRIPTS_DIR / script), *arguments]
    print(f"\n> {' '.join(command)}")
    subprocess.run(command, check=True, cwd=ROOT.parent)


def main() -> None:
    parser = ArgumentParser(
        description=(
            "Collect public SDCourse material in Day 1..N order and generate a complete original engineering lesson "
            "for every collected day."
        )
    )
    parser.add_argument("--track", choices=["python-js", "java-spring", "all"], default="python-js")
    parser.add_argument("--resume", action="store_true", help="Skip lesson records already in the manifest.")
    parser.add_argument("--max-lessons", type=int, help="Limit each selected track for a smoke test.")
    parser.add_argument("--rebuild-context", action="store_true", help="Also rebuild SQLite/FTS context artifacts.")
    parser.add_argument("--chunk-size", type=int, default=1800)
    parser.add_argument("--overlap", type=int, default=180)
    args = parser.parse_args()

    tracks = list(TRACK_SOURCES) if args.track == "all" else [args.track]
    source_names = [TRACK_SOURCES[track] for track in tracks]

    collection_args: list[str] = []
    for source_name in source_names:
        collection_args.extend(["--source", source_name])
    if args.resume:
        collection_args.append("--resume")
    if args.max_lessons is not None:
        collection_args.extend(["--max-articles", str(args.max_lessons)])
    run("collect.py", *collection_args)

    guide_args: list[str] = []
    for source_name in source_names:
        guide_args.extend(["--source", source_name])
    run("build_course_guide.py", *guide_args)
    run("build_index.py")

    if args.rebuild_context:
        run(
            "build_context.py",
            "--chunk-size",
            str(args.chunk_size),
            "--overlap",
            str(args.overlap),
        )

    print("\nSDCourse learning notes are ready under engineering-knowledge-base/output.")
    print("For scheduled day-wise learning, use scripts/run_daily_course_learning.py.")


if __name__ == "__main__":
    main()

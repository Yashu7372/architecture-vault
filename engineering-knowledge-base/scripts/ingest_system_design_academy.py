from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"


def run(script: str, *arguments: str) -> None:
    command = [sys.executable, str(SCRIPTS_DIR / script), *arguments]
    print(f"\n> {' '.join(command)}")
    subprocess.run(command, check=True, cwd=ROOT.parent)


def main() -> None:
    parser = ArgumentParser(
        description="Validate, ingest, index, and build retrieval context for System Design Academy."
    )
    parser.add_argument("--resume", action="store_true", help="Skip article URLs already in the manifest.")
    parser.add_argument("--max-articles", type=int, help="Limit article ingestion for a smoke test.")
    parser.add_argument("--skip-validation", action="store_true", help="Skip the catalog link-health report.")
    parser.add_argument("--fail-on-dead-links", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--chunk-size", type=int, default=1800)
    parser.add_argument("--overlap", type=int, default=180)
    args = parser.parse_args()

    if not args.skip_validation:
        validation_args = [
            "--source",
            "system-design-academy",
            "--workers",
            str(args.workers),
        ]
        if args.fail_on_dead_links:
            validation_args.append("--fail-on-error")
        run("validate_catalog.py", *validation_args)

    collection_args = ["--source", "system-design-academy"]
    if args.resume:
        collection_args.append("--resume")
    if args.max_articles is not None:
        collection_args.extend(["--max-articles", str(args.max_articles)])
    run("collect.py", *collection_args)

    run("build_index.py")
    run(
        "build_context.py",
        "--chunk-size",
        str(args.chunk_size),
        "--overlap",
        str(args.overlap),
    )

    print("\nSystem Design Academy context layer is ready under engineering-knowledge-base/output.")


if __name__ == "__main__":
    main()

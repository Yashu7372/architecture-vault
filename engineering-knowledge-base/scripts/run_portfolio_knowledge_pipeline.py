from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
GROUPS_FILE = ROOT / "config" / "source-groups.yaml"
CONFIG_FILES = (
    ROOT / "config" / "sources.manual.yaml",
    ROOT / "config" / "sources.generated.yaml",
)
OUTPUT_DIR = ROOT / "output"


def load_source_names() -> set[str]:
    names: set[str] = set()
    for path in CONFIG_FILES:
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for source in data.get("sources", []):
            name = str(source.get("name", "")).strip()
            if name:
                if name in names:
                    raise ValueError(f"Duplicate source name in registry: {name}")
                names.add(name)
    return names


def load_groups() -> dict[str, dict]:
    if not GROUPS_FILE.exists():
        raise FileNotFoundError(f"Missing source group configuration: {GROUPS_FILE}")
    data = yaml.safe_load(GROUPS_FILE.read_text(encoding="utf-8")) or {}
    groups = data.get("groups", {})
    if not isinstance(groups, dict) or not groups:
        raise ValueError("source-groups.yaml must contain a non-empty 'groups' mapping")
    return groups


def validate_groups(groups: dict[str, dict], configured_sources: set[str]) -> None:
    errors: list[str] = []
    for group_name, group in groups.items():
        sources = group.get("sources", [])
        if not sources:
            errors.append(f"Group '{group_name}' has no sources")
            continue
        duplicates = sorted({name for name in sources if sources.count(name) > 1})
        if duplicates:
            errors.append(f"Group '{group_name}' contains duplicates: {', '.join(duplicates)}")
        missing = sorted(set(sources) - configured_sources)
        if missing:
            errors.append(f"Group '{group_name}' references unknown sources: {', '.join(missing)}")
    if errors:
        raise ValueError("Invalid source group configuration:\n- " + "\n- ".join(errors))


def run(command: list[str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT.parent, check=True)


def parse_args():
    parser = ArgumentParser(
        description="Run the canonical Architecture Vault pipeline used by the portfolio knowledge system."
    )
    parser.add_argument(
        "--group",
        default="canonical-public",
        help="Source group from config/source-groups.yaml (default: canonical-public).",
    )
    parser.add_argument(
        "--source",
        action="append",
        help="Explicit source name. When supplied, replaces the configured group selection. Repeat as needed.",
    )
    parser.add_argument("--resume", action="store_true", help="Skip URLs already present in the local manifest.")
    parser.add_argument(
        "--max-articles",
        type=int,
        help="Bound article collection for collectors that support max_articles.",
    )
    parser.add_argument(
        "--validate-catalog",
        action="store_true",
        help="Validate the System Design Academy catalog before collection when it is selected.",
    )
    parser.add_argument("--skip-index", action="store_true", help="Do not rebuild Markdown indexes.")
    parser.add_argument("--skip-context", action="store_true", help="Do not rebuild retrieval chunks/SQLite context.")
    parser.add_argument("--list-groups", action="store_true", help="Print configured groups and exit.")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate registry/group configuration without performing network collection.",
    )
    return parser.parse_args()


def expected_outputs(skip_index: bool, skip_context: bool) -> list[Path]:
    paths = [OUTPUT_DIR / "manifest.json"]
    if not skip_index:
        paths.append(OUTPUT_DIR / "MASTER_INDEX.md")
    if not skip_context:
        paths.extend(
            [
                OUTPUT_DIR / "context" / "context.sqlite",
                OUTPUT_DIR / "context" / "chunks.jsonl",
                OUTPUT_DIR / "context" / "graph.json",
                OUTPUT_DIR / "context" / "CONTEXT_INDEX.md",
            ]
        )
    return paths


def print_groups(groups: dict[str, dict]) -> None:
    for name, group in groups.items():
        print(f"{name}: {group.get('description', '')}")
        for source in group.get("sources", []):
            print(f"  - {source}")


def main() -> int:
    args = parse_args()
    configured_sources = load_source_names()
    groups = load_groups()
    validate_groups(groups, configured_sources)

    if args.list_groups:
        print_groups(groups)
        return 0

    if args.source:
        selected_sources = args.source
    else:
        if args.group not in groups:
            raise ValueError(
                f"Unknown group '{args.group}'. Available groups: {', '.join(sorted(groups))}"
            )
        selected_sources = list(groups[args.group].get("sources", []))

    unknown = sorted(set(selected_sources) - configured_sources)
    if unknown:
        raise ValueError(f"Unknown source(s): {', '.join(unknown)}")

    print(
        json.dumps(
            {
                "group": None if args.source else args.group,
                "sources": selected_sources,
                "resume": args.resume,
                "max_articles": args.max_articles,
                "validate_catalog": args.validate_catalog,
                "skip_index": args.skip_index,
                "skip_context": args.skip_context,
            },
            indent=2,
        )
    )

    if args.validate_only:
        print("Portfolio knowledge registry validation: PASS")
        return 0

    python = sys.executable

    if args.validate_catalog and "system-design-academy" in selected_sources:
        run(
            [
                python,
                str(ROOT / "scripts" / "validate_catalog.py"),
                "--source",
                "system-design-academy",
                "--fail-on-error",
            ]
        )

    collect_command = [python, str(ROOT / "scripts" / "collect.py")]
    for source in selected_sources:
        collect_command.extend(["--source", source])
    if args.resume:
        collect_command.append("--resume")
    if args.max_articles is not None:
        collect_command.extend(["--max-articles", str(args.max_articles)])
    run(collect_command)

    if not args.skip_index:
        run([python, str(ROOT / "scripts" / "build_index.py")])

    if not args.skip_context:
        run([python, str(ROOT / "scripts" / "build_context.py")])

    missing = [str(path.relative_to(ROOT)) for path in expected_outputs(args.skip_index, args.skip_context) if not path.is_file()]
    if missing:
        raise RuntimeError("Pipeline completed but required output is missing:\n- " + "\n- ".join(missing))

    manifest = json.loads((OUTPUT_DIR / "manifest.json").read_text(encoding="utf-8"))
    source_counts: dict[str, int] = {}
    for item in manifest:
        name = item.get("source_name", "unknown")
        source_counts[name] = source_counts.get(name, 0) + 1

    print(
        json.dumps(
            {
                "status": "PASS",
                "documents": len(manifest),
                "source_counts": dict(sorted(source_counts.items())),
                "output": str(OUTPUT_DIR),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

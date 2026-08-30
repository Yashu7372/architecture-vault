from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
import json
import subprocess
import sys
import uuid

import yaml

ROOT = Path(__file__).resolve().parents[1]
GROUPS_FILE = ROOT / "config" / "source-groups.yaml"
CONFIG_FILES = (
    ROOT / "config" / "sources.manual.yaml",
    ROOT / "config" / "sources.generated.yaml",
)
OUTPUT_DIR = ROOT / "output"


def load_sources() -> list[dict]:
    sources: list[dict] = []
    for path in CONFIG_FILES:
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        sources.extend(data.get("sources", []))
    return sources


def load_source_names() -> set[str]:
    names: set[str] = set()
    for source in load_sources():
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
        description="Run the canonical Architecture Vault capability pipeline used by the portfolio knowledge system."
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
        help="Validate registry/group/capability contracts without performing network collection.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run read-only collector capabilities and evidence capture without mutating the manifest/context.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail the pipeline when any selected collector capability fails.",
    )
    parser.add_argument("--run-id", help="Optional run id supplied by an external Control Plane.")
    return parser.parse_args()


def expected_outputs(skip_index: bool, skip_context: bool, run_id: str) -> list[Path]:
    paths = [
        OUTPUT_DIR / "manifest.json",
        OUTPUT_DIR / "deltas" / "latest.json",
        OUTPUT_DIR / "state" / "source-state.json",
        OUTPUT_DIR / "evidence" / run_id / "run-summary.json",
    ]
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

    run_id = args.run_id or f"vault-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    summary = {
        "run_id": run_id,
        "group": None if args.source else args.group,
        "sources": selected_sources,
        "resume": args.resume,
        "max_articles": args.max_articles,
        "validate_catalog": args.validate_catalog,
        "skip_index": args.skip_index,
        "skip_context": args.skip_context,
        "dry_run": args.dry_run,
        "strict": args.strict,
    }
    print(json.dumps(summary, indent=2))

    python = sys.executable

    # Fail before any network work if a source type is not backed by a declared
    # capability or a capability violates the read-only collector contract.
    run([python, str(ROOT / "scripts" / "validate_capabilities.py"), "--json"])

    if args.validate_only:
        print("Portfolio knowledge registry + capability validation: PASS")
        return 0

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

    collect_command = [
        python,
        str(ROOT / "scripts" / "collect.py"),
        "--run-id",
        run_id,
    ]
    for source in selected_sources:
        collect_command.extend(["--source", source])
    if args.resume:
        collect_command.append("--resume")
    if args.max_articles is not None:
        collect_command.extend(["--max-articles", str(args.max_articles)])
    if args.dry_run:
        collect_command.append("--dry-run")
    if args.strict:
        collect_command.append("--strict")
    run(collect_command)

    if args.dry_run:
        evidence_summary = OUTPUT_DIR / "evidence" / run_id / "run-summary.json"
        if not evidence_summary.is_file():
            raise RuntimeError(f"Dry run completed without evidence summary: {evidence_summary}")
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "mode": "dry-run",
                    "run_id": run_id,
                    "evidence": str(evidence_summary),
                },
                indent=2,
            )
        )
        return 0

    if not args.skip_index:
        run([python, str(ROOT / "scripts" / "build_index.py")])

    if not args.skip_context:
        run([python, str(ROOT / "scripts" / "build_context.py")])

    missing = [
        str(path.relative_to(ROOT))
        for path in expected_outputs(args.skip_index, args.skip_context, run_id)
        if not path.is_file()
    ]
    if missing:
        raise RuntimeError("Pipeline completed but required output is missing:\n- " + "\n- ".join(missing))

    manifest = json.loads((OUTPUT_DIR / "manifest.json").read_text(encoding="utf-8"))
    source_counts: dict[str, int] = {}
    for item in manifest:
        name = item.get("source_name", "unknown")
        source_counts[name] = source_counts.get(name, 0) + 1

    delta = json.loads((OUTPUT_DIR / "deltas" / "latest.json").read_text(encoding="utf-8"))
    evidence = json.loads(
        (OUTPUT_DIR / "evidence" / run_id / "run-summary.json").read_text(encoding="utf-8")
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "run_id": run_id,
                "documents": len(manifest),
                "source_counts": dict(sorted(source_counts.items())),
                "knowledge_delta_changes": delta.get("change_count", 0),
                "knowledge_delta_counts": delta.get("change_counts", {}),
                "capability_status_counts": evidence.get("status_counts", {}),
                "flagged_external_documents": evidence.get("flagged_documents", 0),
                "output": str(OUTPUT_DIR),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

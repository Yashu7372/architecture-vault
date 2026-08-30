from __future__ import annotations

from argparse import ArgumentParser
from pathlib import Path
import json
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from capabilities.registry import CapabilityRegistry

SOURCE_FILES = (
    ROOT / "config" / "sources.manual.yaml",
    ROOT / "config" / "sources.generated.yaml",
)


def load_sources() -> list[dict]:
    sources: list[dict] = []
    for path in SOURCE_FILES:
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        sources.extend(data.get("sources", []))
    return sources


def validate() -> dict:
    registry = CapabilityRegistry.default(ROOT)
    sources = load_sources()
    errors = registry.validate_all_sources(sources)
    instantiated: list[str] = []

    for manifest in registry.manifests():
        try:
            registry.create_collector(manifest)
            instantiated.append(manifest.capability_id)
        except Exception as exc:
            errors.append(f"{manifest.capability_id}: {type(exc).__name__}: {exc}")

    source_types = sorted({str(source.get("type", "")) for source in sources if source.get("type")})
    registered_types = sorted({source_type for manifest in registry.manifests() for source_type in manifest.source_types})
    missing = sorted(set(source_types) - set(registered_types))
    if missing:
        errors.append(f"Unregistered source types: {', '.join(missing)}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "capabilities": len(registry.manifests()),
        "sources": len(sources),
        "source_types": source_types,
        "registered_source_types": registered_types,
        "instantiated_capabilities": sorted(instantiated),
        "external_write_capabilities": [
            manifest.capability_id for manifest in registry.manifests() if manifest.external_writes
        ],
        "errors": errors,
    }


def main() -> int:
    parser = ArgumentParser(description="Validate Architecture Vault collector capabilities without network I/O.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON only.")
    args = parser.parse_args()

    result = validate()
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Capability validation: {result['status']}")
        print(f"Capabilities: {result['capabilities']}")
        print(f"Sources: {result['sources']}")
        print(f"Source types: {', '.join(result['source_types'])}")
        if result["errors"]:
            for error in result["errors"]:
                print(f"- {error}")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

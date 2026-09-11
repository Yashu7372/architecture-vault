from __future__ import annotations

from argparse import ArgumentParser
from datetime import datetime, timezone
from pathlib import Path
import json
import re

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = REPO_ROOT / "portfolio-spine" / "data" / "spine.json"
SCHEMA_VERSION = "portfolio-spine.v1"
GRAPH_REPO_URL = "https://github.com/Yashu7372/enterprise-architecture-graph"
FLAGSHIP_REPOS = {
    "forge": "https://github.com/Yashu7372/engineering-control-plane",
}

SECTION_PRIORITY = {
    "problem": ["problem"],
    "mental_model": ["mental model", "purpose"],
    "how_it_works": [
        "reference flow",
        "core semantics",
        "functional behavior",
        "design principles",
        "principle",
        "output",
    ],
    "tradeoffs": [
        "failure modes",
        "trade-offs and alternatives",
        "important consequence",
        "important distinction",
        "durable execution requirements",
    ],
}


def _clean_inline(value: str) -> str:
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    value = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", value)
    return " ".join(value.split())


def _trim_words(value: str, limit: int) -> str:
    words = value.split()
    if len(words) <= limit:
        return value
    return " ".join(words[:limit]).rstrip(" ,.;:") + "…"


def _section_key(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def parse_markdown(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    title = ""
    graph_id = ""
    metadata: dict[str, str] = {}
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    in_fence = False

    def flush() -> None:
        nonlocal buffer
        if current is None:
            buffer = []
            return
        cleaned: list[str] = []
        for line in buffer:
            stripped = line.strip()
            if not stripped:
                if cleaned and cleaned[-1] != "":
                    cleaned.append("")
                continue
            if stripped.startswith("-"):
                cleaned.append("• " + _clean_inline(stripped[1:].strip()))
            else:
                cleaned.append(_clean_inline(stripped))
        value = "\n".join(cleaned).strip()
        if value:
            sections[current] = value
        buffer = []

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if line.startswith("# ") and not title:
            title = _clean_inline(line[2:])
            continue
        if line.startswith("## ") and not in_fence:
            flush()
            current = _section_key(line[3:])
            continue
        if current is not None:
            buffer.append(line)
            continue
        match = re.match(r"\*\*([^*]+):\*\*\s*`?([^`]+?)`?\s{0,2}$", line)
        if match:
            metadata[_section_key(match.group(1))] = _clean_inline(match.group(2))

    flush()
    graph_id = metadata.get("graph id", "")
    return {
        "title": title or path.stem.replace("-", " ").title(),
        "graph_id": graph_id,
        "metadata": metadata,
        "sections": sections,
        "path": path,
    }


def pick_section(document: dict | None, candidates: list[str], word_limit: int = 95) -> str:
    if not document:
        return ""
    sections = document.get("sections", {})
    for name in candidates:
        value = sections.get(name)
        if value:
            return _trim_words(value, word_limit)
    return ""


def discover_documents(graph_root: Path, nodes: list[dict]) -> dict[str, dict]:
    documents: dict[str, dict] = {}
    for directory in (graph_root / "knowledge", graph_root / "architectures"):
        if not directory.exists():
            continue
        for path in directory.rglob("*.md"):
            if path.name.upper().endswith("TEMPLATE.MD"):
                continue
            document = parse_markdown(path)
            if document["graph_id"]:
                documents[document["graph_id"]] = document

    # Architecture/project documents currently do not require Graph ID metadata.
    # Match them by a conservative filename prefix only, e.g. forge-*.md.
    for node in nodes:
        if node.get("id") in documents:
            continue
        if node.get("type") not in {"project", "lab"}:
            continue
        architecture_dir = graph_root / "architectures"
        if not architecture_dir.exists():
            continue
        matches = sorted(architecture_dir.glob(f"{node['id']}-*.md"))
        if len(matches) == 1:
            documents[node["id"]] = parse_markdown(matches[0])
    return documents


def relation_index(relationships: list[dict]) -> dict[str, list[dict]]:
    index: dict[str, list[dict]] = {}
    for relation in relationships:
        index.setdefault(relation["from"], []).append(relation)
        index.setdefault(relation["to"], []).append(relation)
    return index


def github_blob_url(path: Path, graph_root: Path) -> str:
    relative = path.relative_to(graph_root).as_posix()
    return f"{GRAPH_REPO_URL}/blob/main/{relative}"


def build_item(node: dict, document: dict | None, attached_relations: list[dict], graph_root: Path) -> dict:
    summary = str(node.get("summary") or "").strip()
    problem = pick_section(document, SECTION_PRIORITY["problem"]) or summary
    mental_model = pick_section(document, SECTION_PRIORITY["mental_model"]) or summary
    how_it_works = pick_section(document, SECTION_PRIORITY["how_it_works"]) or summary
    tradeoffs = pick_section(document, SECTION_PRIORITY["tradeoffs"])
    if not tradeoffs:
        tradeoffs = "Use the connected knowledge and lab evidence to inspect the operational trade-offs before applying this idea."

    kind = "lab" if node.get("type") in {"project", "lab"} else "article"
    provenance: list[dict] = []
    if document:
        provenance.append(
            {
                "label": "Reference architecture" if kind == "lab" else "Curated knowledge node",
                "path": document["path"].relative_to(graph_root).as_posix(),
                "url": github_blob_url(document["path"], graph_root),
            }
        )
    else:
        provenance.append(
            {
                "label": "Curated graph node",
                "path": "graph/nodes.yaml",
                "url": f"{GRAPH_REPO_URL}/blob/main/graph/nodes.yaml",
            }
        )

    evidence: list[dict] = []
    repo = FLAGSHIP_REPOS.get(node["id"])
    if repo:
        evidence.append({"label": f"{node['name']} implementation", "detail": "Flagship portfolio repository", "url": repo})

    return {
        "node_id": node["id"],
        "slug": node["id"],
        "kind": kind,
        "title": node["name"],
        "domain": node.get("domain") or "architecture",
        "maturity": node.get("maturity") or "DISCOVERED",
        "summary": summary or problem,
        "two_minute_read": {
            "problem": problem,
            "mental_model": mental_model,
            "how_it_works": how_it_works,
            "tradeoffs": tradeoffs,
            "takeaway": summary or mental_model,
        },
        "relationships": attached_relations,
        "evidence": evidence,
        "provenance": provenance,
    }


def build_spine(graph_root: Path) -> dict:
    node_file = graph_root / "graph" / "nodes.yaml"
    relationship_file = graph_root / "graph" / "relationships.yaml"
    if not node_file.is_file() or not relationship_file.is_file():
        raise FileNotFoundError(
            f"{graph_root} is not an Enterprise Architecture Graph checkout: graph/nodes.yaml and graph/relationships.yaml are required."
        )

    node_doc = yaml.safe_load(node_file.read_text(encoding="utf-8")) or {}
    relationship_doc = yaml.safe_load(relationship_file.read_text(encoding="utf-8")) or {}
    nodes = list(node_doc.get("nodes") or [])
    relationships = list(relationship_doc.get("relationships") or [])
    documents = discover_documents(graph_root, nodes)
    rel_index = relation_index(relationships)

    compact_nodes = [
        {
            "id": node["id"],
            "name": node["name"],
            "type": node.get("type"),
            "domain": node.get("domain"),
            "maturity": node.get("maturity"),
        }
        for node in nodes
    ]
    items = [
        build_item(node, documents.get(node["id"]), rel_index.get(node["id"], []), graph_root)
        for node in nodes
    ]
    items.sort(key=lambda item: (item["kind"] != "lab", item["domain"], item["title"]))

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": "generated-from-curated-graph",
        "authorities": {
            "discovery": "Yashu7372/architecture-vault",
            "curated_knowledge": "Yashu7372/enterprise-architecture-graph",
            "implementation_evidence": "flagship repositories",
        },
        "nodes": compact_nodes,
        "relationships": relationships,
        "items": items,
    }


def main() -> int:
    parser = ArgumentParser(description="Build the public-safe portfolio Knowledge Spine read model.")
    parser.add_argument(
        "--graph-root",
        type=Path,
        default=REPO_ROOT.parent / "enterprise-architecture-graph",
        help="Local checkout of Yashu7372/enterprise-architecture-graph.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    spine = build_spine(args.graph_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(spine, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "schema_version": SCHEMA_VERSION,
                "articles": sum(1 for item in spine["items"] if item["kind"] == "article"),
                "labs": sum(1 for item in spine["items"] if item["kind"] == "lab"),
                "relationships": len(spine["relationships"]),
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

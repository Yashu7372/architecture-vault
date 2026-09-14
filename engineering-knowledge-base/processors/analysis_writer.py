from __future__ import annotations

from pathlib import Path
import json

from slugify import slugify


REQUIRED_TOP_LEVEL = {
    "schema_version",
    "source_id",
    "title",
    "ten_minute_digest",
    "concepts",
    "patterns",
    "relationships",
    "evidence_claims",
}


class AnalysisValidationError(ValueError):
    pass


def validate_analysis(data: dict) -> None:
    missing = REQUIRED_TOP_LEVEL - set(data)
    if missing:
        raise AnalysisValidationError(f"Missing required fields: {sorted(missing)}")
    if data.get("schema_version") != "1.0":
        raise AnalysisValidationError("Unsupported schema_version")
    if not isinstance(data.get("concepts"), list):
        raise AnalysisValidationError("concepts must be a list")
    if not isinstance(data.get("patterns"), list):
        raise AnalysisValidationError("patterns must be a list")
    if not isinstance(data.get("relationships"), list):
        raise AnalysisValidationError("relationships must be a list")
    if not isinstance(data.get("evidence_claims"), list):
        raise AnalysisValidationError("evidence_claims must be a list")


class AnalysisWriter:
    def __init__(self, root: Path):
        self.root = root
        self.digests = root / "output" / "digests"
        self.concepts = root / "output" / "concepts"
        self.patterns = root / "output" / "patterns"
        self.graph_dir = root / "output" / "graph"
        for directory in (self.digests, self.concepts, self.patterns, self.graph_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def apply(self, data: dict) -> dict:
        validate_analysis(data)
        digest_path = self._write_digest(data)
        concept_paths = self._write_concepts(data)
        pattern_paths = self._write_patterns(data)
        self._merge_relationships(data)
        return {
            "digest": str(digest_path.relative_to(self.root)),
            "concepts": [str(p.relative_to(self.root)) for p in concept_paths],
            "patterns": [str(p.relative_to(self.root)) for p in pattern_paths],
        }

    def _write_digest(self, data: dict) -> Path:
        d = data["ten_minute_digest"]
        lines = [
            "---",
            f"source_id: {data['source_id']}",
            f"quality_score: {data.get('quality_score', '')}",
            f"difficulty: {data.get('difficulty', '')}",
            "---",
            "",
            f"# {data['title']}",
            "",
            "## Why This Matters",
            d.get("why_it_matters", ""),
            "",
            "## Prerequisites",
            *[f"- {x}" for x in d.get("prerequisites", [])],
            "",
            "## Core Idea",
            d.get("core_idea", ""),
            "",
            "## Architecture",
            d.get("architecture", ""),
            "",
            "## Key Takeaways",
            *[f"- {x}" for x in d.get("key_takeaways", [])],
            "",
            "## Trade-offs",
            *[f"- {x}" for x in d.get("tradeoffs", [])],
            "",
            "## Production Concerns",
            *[f"- {x}" for x in d.get("production_concerns", [])],
            "",
            "## Anti-patterns",
            *[f"- {x}" for x in d.get("anti_patterns", [])],
            "",
            "## Implementation Ideas",
            *[f"- {x}" for x in d.get("implementation_ideas", [])],
            "",
            "## Evidence-backed Claims",
            *[
                f"- **{c.get('claim', '')}** — {c.get('evidence', '')}"
                + (f" ({c.get('location')})" if c.get("location") else "")
                for c in data.get("evidence_claims", [])
            ],
            "",
            "## Final 10-Minute Takeaway",
            d.get("final_takeaway", ""),
            "",
        ]
        path = self.digests / f"{data['source_id']}-{slugify(data['title'])[:80]}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def _write_concepts(self, data: dict) -> list[Path]:
        paths = []
        for concept in data.get("concepts", []):
            name = concept.get("name", "").strip()
            if not name:
                continue
            path = self.concepts / f"{slugify(name)}.md"
            existing = path.read_text(encoding="utf-8") if path.exists() else f"# {name}\n\n"
            marker = f"<!-- source:{data['source_id']} -->"
            if marker not in existing:
                existing += (
                    f"\n## Source Contribution: {data['title']}\n\n"
                    f"{marker}\n\n"
                    f"{concept.get('definition', '')}\n\n"
                    f"Importance: {concept.get('importance', 'important')}\n"
                )
                path.write_text(existing, encoding="utf-8")
            paths.append(path)
        return paths

    def _write_patterns(self, data: dict) -> list[Path]:
        paths = []
        for pattern in data.get("patterns", []):
            name = pattern.get("name", "").strip()
            if not name:
                continue
            path = self.patterns / f"{slugify(name)}.md"
            existing = path.read_text(encoding="utf-8") if path.exists() else f"# {name}\n\n"
            marker = f"<!-- source:{data['source_id']} -->"
            if marker not in existing:
                existing += (
                    f"\n## Evidence from {data['title']}\n\n"
                    f"{marker}\n\n"
                    f"### Problem\n{pattern.get('problem', '')}\n\n"
                    f"### Guidance\n{pattern.get('guidance', '')}\n\n"
                    "### When to Use\n"
                    + "\n".join(f"- {x}" for x in pattern.get("when_to_use", []))
                    + "\n\n### When Not to Use\n"
                    + "\n".join(f"- {x}" for x in pattern.get("when_not_to_use", []))
                    + "\n"
                )
                path.write_text(existing, encoding="utf-8")
            paths.append(path)
        return paths

    def _merge_relationships(self, data: dict) -> None:
        path = self.graph_dir / "relationships.jsonl"
        existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        existing_keys = set()
        for line in existing_lines:
            try:
                item = json.loads(line)
                existing_keys.add((item.get("from"), item.get("type"), item.get("to"), item.get("source_id")))
            except json.JSONDecodeError:
                continue

        output = list(existing_lines)
        for relationship in data.get("relationships", []):
            item = dict(relationship)
            item["source_id"] = data["source_id"]
            key = (item.get("from"), item.get("type"), item.get("to"), item.get("source_id"))
            if key not in existing_keys:
                output.append(json.dumps(item, ensure_ascii=False))
                existing_keys.add(key)
        path.write_text("\n".join(output) + ("\n" if output else ""), encoding="utf-8")

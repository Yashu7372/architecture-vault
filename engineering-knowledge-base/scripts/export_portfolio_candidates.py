from __future__ import annotations

from argparse import ArgumentParser
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from processing.knowledge_enrichment import concept_relation_statistics, digest

OUTPUT_DIR = ROOT / "output"
CONTEXT_DIR = OUTPUT_DIR / "context"
CHUNKS_FILE = CONTEXT_DIR / "chunks.jsonl"
TAXONOMY_FILE = ROOT / "config" / "knowledge-taxonomy.yaml"
EXPORT_DIR = OUTPUT_DIR / "exports"
DEFAULT_EXPORT = EXPORT_DIR / "portfolio-candidates.v1.json"
SCHEMA_VERSION = "portfolio-candidates.v1"


def _normalized(value: str) -> str:
    return " ".join(str(value).lower().split())


def _contains_term(text: str, term: str) -> bool:
    text = _normalized(text)
    term = _normalized(term)
    if not term:
        return False
    # Word boundaries make short seed terms such as CAP/HTTP safe while still
    # allowing punctuation-heavy phrases to fall back to exact containment.
    if re.fullmatch(r"[a-z0-9][a-z0-9 ._-]*", term):
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None
    return term in text


def score_concept_in_chunk(concept: dict, chunk: dict) -> tuple[float, str, list[str], list[str]] | None:
    text = f"{chunk.get('heading', '')}\n{chunk.get('text', '')}"
    explicit_terms = [concept.get("name", ""), *concept.get("aliases", [])]
    keyword_terms = list(concept.get("keywords", []))
    explicit_hits = sorted({term for term in explicit_terms if _contains_term(text, str(term))})
    keyword_hits = sorted({term for term in keyword_terms if _contains_term(text, str(term))})

    if explicit_hits:
        score = min(0.96, 0.72 + 0.05 * min(3, len(explicit_hits)) + 0.03 * min(4, len(keyword_hits)))
        return round(score, 4), "EXTRACTED", explicit_hits, keyword_hits
    if len(keyword_hits) >= 2:
        score = min(0.69, 0.38 + 0.07 * min(4, len(keyword_hits)))
        return round(score, 4), "INFERRED", [], keyword_hits
    return None


def build_candidate_export(taxonomy: dict, chunks: list[dict]) -> dict:
    concepts = taxonomy.get("concepts", []) or []
    links: list[dict] = []
    evidence_by_concept: dict[str, list[dict]] = defaultdict(list)

    enriched_chunks: list[dict] = []
    for original in chunks:
        chunk = dict(original)
        chunk.setdefault("evidence_unit_id", chunk.get("document_id"))
        enriched_chunks.append(chunk)
        for concept in concepts:
            match = score_concept_in_chunk(concept, chunk)
            if match is None:
                continue
            score, evidence_state, explicit_hits, keyword_hits = match
            link = {
                "concept_id": concept["id"],
                "chunk_id": chunk["chunk_id"],
                "score": score,
                "evidence_state": evidence_state,
            }
            links.append(link)
            evidence_by_concept[concept["id"]].append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "document_id": chunk.get("document_id"),
                    "heading": chunk.get("heading"),
                    "source_name": chunk.get("source_name"),
                    "url": chunk.get("url"),
                    "score": score,
                    "evidence_state": evidence_state,
                    "explicit_hits": explicit_hits,
                    "keyword_hits": keyword_hits,
                }
            )

    candidate_concepts: list[dict] = []
    for concept in concepts:
        evidence = evidence_by_concept.get(concept["id"], [])
        if not evidence:
            continue
        distinct_documents = {item["document_id"] for item in evidence if item.get("document_id")}
        max_score = max(item["score"] for item in evidence)
        extracted = any(item["evidence_state"] == "EXTRACTED" for item in evidence)
        confidence = min(
            0.97,
            0.65 * max_score
            + 0.20 * min(1.0, len(distinct_documents) / 3.0)
            + 0.15 * min(1.0, len(evidence) / 5.0),
        )
        candidate_concepts.append(
            {
                "candidate_id": f"candidate-concept-{digest(concept['id'])}",
                "kind": "concept",
                "concept_id": concept["id"],
                "name": concept.get("name", concept["id"]),
                "domain": concept.get("domain"),
                "status": "CANDIDATE",
                "evidence_state": "EXTRACTED" if extracted else "INFERRED",
                "confidence": round(confidence, 4),
                "statistics": {
                    "evidence_chunks": len(evidence),
                    "source_documents": len(distinct_documents),
                    "max_chunk_score": round(max_score, 4),
                },
                "evidence": sorted(evidence, key=lambda item: (-item["score"], item["chunk_id"]))[:12],
            }
        )

    relation_candidates = []
    for relation in concept_relation_statistics(links, enriched_chunks):
        relation_candidates.append(
            {
                "candidate_id": relation["relation_id"],
                "kind": "relationship",
                "subject_concept_id": relation["subject_concept_id"],
                "predicate": relation["predicate"],
                "object_concept_id": relation["object_concept_id"],
                "status": "CANDIDATE",
                "evidence_state": relation["evidence_state"],
                "confidence": relation["confidence"],
                "statistics": relation["statistics"],
                "chunk_ids": relation["chunk_ids"],
                "document_ids": relation["document_ids"],
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "producer": "architecture-vault",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "authority": "candidate-only",
        "invariants": [
            "candidate-concepts-are-not-curated-graph-nodes",
            "candidate-relationships-are-not-verified-graph-relationships",
            "every-candidate-retains-source-evidence",
        ],
        "concepts": sorted(candidate_concepts, key=lambda item: (item["domain"] or "", item["concept_id"])),
        "relationships": sorted(
            relation_candidates,
            key=lambda item: (-item["confidence"], item["subject_concept_id"], item["object_concept_id"]),
        ),
    }


def load_chunks(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Missing context chunks: {path}. Run scripts/build_context.py first.")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = ArgumentParser(description="Export evidence-backed Architecture Vault candidates for portfolio curation.")
    parser.add_argument("--chunks", type=Path, default=CHUNKS_FILE)
    parser.add_argument("--taxonomy", type=Path, default=TAXONOMY_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_EXPORT)
    args = parser.parse_args()

    taxonomy = yaml.safe_load(args.taxonomy.read_text(encoding="utf-8")) or {}
    chunks = load_chunks(args.chunks)
    export = build_candidate_export(taxonomy, chunks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(export, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "schema_version": SCHEMA_VERSION,
                "concept_candidates": len(export["concepts"]),
                "relationship_candidates": len(export["relationships"]),
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from urllib.parse import urlparse
import hashlib
import math
import re

import yaml

WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.#/_-]*")
PAGE_HEADING_RE = re.compile(r"^Page\s+(\d+)$", re.IGNORECASE)


@dataclass(frozen=True)
class SourceQuality:
    tier: str
    score: float
    authority: str
    matched_rule: str


@dataclass(frozen=True)
class DuplicateCandidate:
    duplicate_group_id: str
    document_id: str
    representative_document_id: str
    duplicate_type: str
    similarity: float


def digest(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def load_yaml(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return default or {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else (default or {})


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().split(":", 1)[0]
    except Exception:
        return ""


def _matches(value: str, patterns: list[str]) -> bool:
    value = value.lower()
    for pattern in patterns:
        p = str(pattern).strip().lower()
        if not p:
            continue
        if p.startswith("re:"):
            if re.search(p[3:], value, re.IGNORECASE):
                return True
        elif p.startswith("*."):
            suffix = p[1:]
            if value.endswith(suffix):
                return True
        elif p in value:
            return True
    return False


def score_source(document: dict, config: dict) -> SourceQuality:
    source_type = str(document.get("source_type", "")).lower()
    source_name = str(document.get("source_name", "")).lower()
    url = str(document.get("url", ""))
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":", 1)[0]
    path = parsed.path or ""
    metadata = document.get("metadata", {}) or {}

    tiers = config.get("tiers", {}) or {}

    def make(tier: str, authority: str, rule: str) -> SourceQuality:
        score = float((tiers.get(tier, {}) or {}).get("score", {"A": 0.95, "B": 0.78, "C": 0.58, "D": 0.38}.get(tier, 0.38)))
        return SourceQuality(tier=tier, score=score, authority=authority, matched_rule=rule)

    overrides = config.get("metadata_overrides", {}) or {}
    override_tier = next((metadata.get(key) for key in overrides.get("tier_keys", []) if metadata.get(key)), None)
    override_authority = next((metadata.get(key) for key in overrides.get("authority_keys", []) if metadata.get(key)), None)
    if override_tier:
        return make(str(override_tier).upper(), str(override_authority or "metadata-override"), "metadata-override")

    for rule in config.get("host_rules", []) or []:
        if not re.search(str(rule.get("pattern", "")), host, re.IGNORECASE):
            continue
        path_pattern = rule.get("path_pattern")
        if path_pattern and not re.search(str(path_pattern), path, re.IGNORECASE):
            continue
        return make(str(rule.get("tier", "C")), str(rule.get("authority_type", "web-article")), f"host:{rule.get('pattern', '')}")

    for rule in config.get("source_name_rules", []) or []:
        if re.search(str(rule.get("pattern", "")), source_name, re.IGNORECASE):
            return make(str(rule.get("tier", "C")), str(rule.get("authority_type", "source")), f"source:{rule.get('pattern', '')}")

    default = (config.get("defaults_by_source_type", {}) or {}).get(source_type, {}) or {}
    if default:
        return make(str(default.get("tier", "C")), str(default.get("authority_type", source_type or "unknown")), f"type:{source_type}")

    # Backward-compatible simple rule form used by focused unit tests.
    for rule in config.get("rules", []) or []:
        when = rule.get("when", {}) or {}
        type_match = not when.get("source_types") or source_type in {str(v).lower() for v in when.get("source_types", [])}
        name_match = not when.get("source_names") or _matches(source_name, list(when.get("source_names", [])))
        host_match = not when.get("domains") or _matches(host, list(when.get("domains", [])))
        if type_match and name_match and host_match:
            return SourceQuality(str(rule.get("tier", "C")), float(rule.get("score", 0.5)), str(rule.get("authority", "secondary")), str(rule.get("id", "unnamed")))

    simple_default = config.get("default", {}) or {}
    if simple_default:
        return SourceQuality(str(simple_default.get("tier", "C")), float(simple_default.get("score", 0.45)), str(simple_default.get("authority", "discovery")), "default")
    return make("D", "unknown", "fallback")

def normalize_for_dedupe(text: str) -> str:
    words = [w.lower() for w in WORD_RE.findall(text)]
    return " ".join(words)


def exact_fingerprint(text: str) -> str:
    return hashlib.sha256(normalize_for_dedupe(text).encode("utf-8")).hexdigest()


def simhash64(text: str) -> int:
    tokens = normalize_for_dedupe(text).split()
    if not tokens:
        return 0
    shingles: list[str] = []
    if len(tokens) < 4:
        shingles = tokens
    else:
        shingles = [" ".join(tokens[i : i + 4]) for i in range(len(tokens) - 3)]
    vector = [0] * 64
    counts = Counter(shingles)
    for shingle, weight in counts.items():
        h = int(hashlib.sha1(shingle.encode("utf-8")).hexdigest()[:16], 16)
        for bit in range(64):
            vector[bit] += weight if (h >> bit) & 1 else -weight
    result = 0
    for bit, value in enumerate(vector):
        if value >= 0:
            result |= 1 << bit
    return result


def hamming_distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def detect_document_duplicates(processed_documents: list[tuple[dict, object]], max_hamming: int = 5) -> list[DuplicateCandidate]:
    exact_groups: dict[str, list[str]] = defaultdict(list)
    simhashes: dict[str, int] = {}
    text_lengths: dict[str, int] = {}

    for document, processed in processed_documents:
        document_id = document["document_id"]
        text = getattr(processed, "canonical_text", "")
        exact_groups[exact_fingerprint(text)].append(document_id)
        simhashes[document_id] = simhash64(text)
        text_lengths[document_id] = max(1, len(normalize_for_dedupe(text)))

    result: list[DuplicateCandidate] = []
    assigned: set[str] = set()
    for fp, ids in exact_groups.items():
        if len(ids) < 2:
            continue
        representative = sorted(ids)[0]
        group_id = f"dup-exact-{fp[:12]}"
        for document_id in sorted(ids):
            result.append(DuplicateCandidate(group_id, document_id, representative, "EXACT", 1.0))
            assigned.add(document_id)

    remaining = sorted(document_id for document_id in simhashes if document_id not in assigned)
    # Band the 64-bit simhash into four 16-bit buckets so we avoid a full O(n^2) scan.
    buckets: dict[tuple[int, int], list[str]] = defaultdict(list)
    for document_id in remaining:
        value = simhashes[document_id]
        for band in range(4):
            buckets[(band, (value >> (band * 16)) & 0xFFFF)].append(document_id)

    checked: set[tuple[str, str]] = set()
    adjacency: dict[str, set[str]] = defaultdict(set)
    for ids in buckets.values():
        if len(ids) < 2:
            continue
        ids = sorted(set(ids))
        for i, left in enumerate(ids):
            for right in ids[i + 1 :]:
                pair = (left, right)
                if pair in checked:
                    continue
                checked.add(pair)
                # Extremely different length documents should not be near duplicates.
                ratio = min(text_lengths[left], text_lengths[right]) / max(text_lengths[left], text_lengths[right])
                if ratio < 0.72:
                    continue
                distance = hamming_distance(simhashes[left], simhashes[right])
                if distance <= max_hamming:
                    adjacency[left].add(right)
                    adjacency[right].add(left)

    visited: set[str] = set()
    for seed in sorted(adjacency):
        if seed in visited:
            continue
        stack = [seed]
        component: list[str] = []
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            stack.extend(adjacency[current] - visited)
        if len(component) < 2:
            continue
        representative = sorted(component)[0]
        group_id = f"dup-near-{digest(':'.join(sorted(component)), 12)}"
        rep_hash = simhashes[representative]
        for document_id in sorted(component):
            distance = hamming_distance(rep_hash, simhashes[document_id])
            similarity = max(0.0, 1.0 - distance / 64.0)
            result.append(DuplicateCandidate(group_id, document_id, representative, "NEAR", round(similarity, 4)))
    return result


def parse_page_number(heading_path: list[str] | None, heading: str | None = None) -> int | None:
    candidates = list(reversed(heading_path or []))
    if heading:
        candidates.insert(0, heading)
    for value in candidates:
        match = PAGE_HEADING_RE.match(str(value).strip())
        if match:
            return int(match.group(1))
    return None


def concept_relation_statistics(concept_links: list[dict], chunks: list[dict], min_score: float = 0.35) -> list[dict]:
    chunk_lookup = {chunk["chunk_id"]: chunk for chunk in chunks}
    chunk_concepts: dict[str, set[str]] = defaultdict(set)
    concept_chunks: dict[str, set[str]] = defaultdict(set)
    concept_units: dict[str, set[str]] = defaultdict(set)

    for link in concept_links:
        if float(link.get("score", 0)) < min_score:
            continue
        cid = link["concept_id"]
        chunk_id = link["chunk_id"]
        chunk_concepts[chunk_id].add(cid)
        concept_chunks[cid].add(chunk_id)
        unit_id = chunk_lookup.get(chunk_id, {}).get("evidence_unit_id") or chunk_lookup.get(chunk_id, {}).get("document_id")
        if unit_id:
            concept_units[cid].add(unit_id)

    all_units = {chunk.get("evidence_unit_id") or chunk.get("document_id") for chunk in chunks if chunk.get("document_id")}
    total_units = max(1, len(all_units))
    pair_chunks: dict[tuple[str, str], set[str]] = defaultdict(set)
    pair_units: dict[tuple[str, str], set[str]] = defaultdict(set)
    for chunk_id, concepts in chunk_concepts.items():
        ids = sorted(concepts)
        unit_id = chunk_lookup.get(chunk_id, {}).get("evidence_unit_id") or chunk_lookup.get(chunk_id, {}).get("document_id")
        for i, left in enumerate(ids):
            for right in ids[i + 1 :]:
                pair = (left, right)
                pair_chunks[pair].add(chunk_id)
                if unit_id:
                    pair_units[pair].add(unit_id)

    relations: list[dict] = []
    for (left, right), evidence_chunks in pair_chunks.items():
        co_chunks = len(evidence_chunks)
        co = len(pair_units[(left, right)])
        docs = co
        if co < 2 or co_chunks < 3:
            continue
        left_count = len(concept_units[left])
        right_count = len(concept_units[right])
        union = left_count + right_count - co
        jaccard = co / max(1, union)
        p_xy = co / total_units
        p_x = left_count / total_units
        p_y = right_count / total_units
        pmi = math.log2(p_xy / max(1e-12, p_x * p_y))
        npmi = pmi / max(1e-12, -math.log2(p_xy)) if p_xy < 1 else 1.0
        support = min(1.0, math.log1p(co) / math.log(25))
        diversity = min(1.0, docs / 5)
        confidence = 0.30 * max(0.0, npmi) + 0.35 * jaccard + 0.20 * support + 0.15 * diversity
        if confidence < 0.22:
            continue
        relations.append({
            "relation_id": f"rel-{digest(f'{left}:STRONGLY_RELATED_TO:{right}')}",
            "subject_concept_id": left,
            "predicate": "STRONGLY_RELATED_TO",
            "object_concept_id": right,
            "confidence": round(min(0.97, confidence), 4),
            "evidence_state": "INFERRED",
            "chunk_ids": sorted(evidence_chunks)[:30],
            "document_ids": sorted(pair_units[(left, right)]),
            "statistics": {
                "cooccurrence_chunks": co_chunks,
                "evidence_units": co,
                "document_diversity": docs,
                "jaccard": round(jaccard, 4),
                "pmi": round(pmi, 4),
                "npmi": round(npmi, 4),
            },
        })
    return sorted(relations, key=lambda item: (-item["confidence"], item["subject_concept_id"], item["object_concept_id"]))


def _cue_hits(text: str, cues: list[str]) -> int:
    lower = text.lower()
    return sum(1 for cue in cues if str(cue).strip() and str(cue).lower() in lower)


def _lens_score(chunk: dict, lens: dict, source_scores: dict[str, SourceQuality]) -> float:
    text = f"{chunk.get('heading', '')} {chunk.get('gist', '')} {chunk.get('text', '')[:1200]}"
    cue_hits = _cue_hits(text, list(lens.get("cue_terms", lens.get("cues", [])) or []))
    source = source_scores.get(chunk.get("document_id", ""))
    authority = source.score if source else 0.38
    concept_signal = max([float(v) for v in chunk.get("concept_scores", {}).values()] or [0.0])
    return 0.45 * min(1.0, cue_hits / 2.0) + 0.35 * authority + 0.20 * concept_signal


def build_multilens_learning_units(
    taxonomy: dict,
    chunks: list[dict],
    concept_links: list[dict],
    source_scores: dict[str, SourceQuality],
    lens_config: dict,
) -> list[dict]:
    concept_lookup = {concept["id"]: concept for concept in taxonomy.get("concepts", [])}
    chunk_lookup = {chunk["chunk_id"]: chunk for chunk in chunks}
    links_by_concept: dict[str, list[dict]] = defaultdict(list)
    for link in concept_links:
        if float(link.get("score", 0)) >= 0.28:
            links_by_concept[link["concept_id"]].append(link)

    for chunk in chunks:
        chunk["concept_scores"] = {}
    for link in concept_links:
        if link["chunk_id"] in chunk_lookup:
            chunk_lookup[link["chunk_id"]]["concept_scores"][link["concept_id"]] = float(link["score"])

    raw_lenses = lens_config.get("lenses", {}) or {}
    if isinstance(raw_lenses, list):
        lenses = [(str(item["id"]), item) for item in raw_lenses]
    else:
        lenses = [(str(lens_id), dict(lens or {})) for lens_id, lens in raw_lenses.items()]

    units: list[dict] = []
    for concept_id, links in links_by_concept.items():
        concept = concept_lookup.get(concept_id)
        if not concept:
            continue
        eligible_chunks = [chunk_lookup[l["chunk_id"]] for l in links if l["chunk_id"] in chunk_lookup]
        if not eligible_chunks:
            continue

        for lens_id, lens in lenses:
            required_authority = set(lens.get("require_authority_types", []) or [])
            lens_cues = list(lens.get("cue_terms", []) or [])
            candidates: list[dict] = []
            for chunk in eligible_chunks:
                source = source_scores.get(chunk["document_id"])
                if required_authority and (not source or source.authority not in required_authority):
                    continue
                text = f"{chunk.get('heading', '')} {chunk.get('gist', '')} {chunk.get('text', '')[:1200]}"
                if lens_cues and _cue_hits(text, lens_cues) == 0 and lens_id not in {"learn"}:
                    continue
                candidates.append(chunk)
            ranked = sorted(
                candidates,
                key=lambda chunk: (-_lens_score(chunk, lens, source_scores), -float(chunk["concept_scores"].get(concept_id, 0)), chunk["chunk_id"]),
            )
            evidence: list[dict] = []
            seen_units: set[str] = set()
            max_evidence = max(4, int(lens.get("min_evidence", 1)) + 2)
            for chunk in ranked:
                unit_id = chunk.get("evidence_unit_id") or chunk["document_id"]
                if unit_id in seen_units:
                    continue
                seen_units.add(unit_id)
                source = source_scores.get(chunk["document_id"])
                evidence.append({
                    "chunk_id": chunk["chunk_id"],
                    "document_id": chunk["document_id"],
                    "evidence_unit_id": unit_id,
                    "title": chunk["title"],
                    "heading": chunk["heading"],
                    "page_number": chunk.get("page_number"),
                    "excerpt": chunk.get("gist", ""),
                    "concept_score": round(float(chunk["concept_scores"].get(concept_id, 0)), 4),
                    "source_tier": source.tier if source else "D",
                    "source_quality_score": source.score if source else 0.38,
                    "authority_type": source.authority if source else "unknown",
                })
                if len(evidence) >= max_evidence:
                    break

            min_evidence = int(lens.get("min_evidence", 1))
            if len(evidence) < min_evidence:
                continue

            sections: list[dict] = []
            for section in lens.get("sections", []) or []:
                section_cues = list(section.get("cues", []) or [])
                ranked_for_section = sorted(
                    evidence,
                    key=lambda item: (-_cue_hits(item["excerpt"], section_cues), -item["source_quality_score"], -item["concept_score"]),
                )
                chosen = ranked_for_section[0] if ranked_for_section else evidence[0]
                sections.append({
                    "id": str(section.get("id", "evidence")),
                    "title": str(section.get("title", section.get("id", "Evidence"))),
                    "extractive_text": chosen["excerpt"],
                    "evidence_chunk_id": chosen["chunk_id"],
                })

            depth = str(lens.get("depth_level", "L1"))
            target_words = int(lens.get("target_words", 360))
            units.append({
                "learning_unit_id": f"unit-{digest(f'{concept_id}:{lens_id}:{depth}')}",
                "concept_id": concept_id,
                "lens": lens_id,
                "depth_level": depth,
                "reading_minutes": max(2, min(3, round(target_words / 150))),
                "title": f"{concept.get('name', concept_id)} — {lens_id.replace('-', ' ').title()}",
                "status": "CANDIDATE_EXTRACTIVE",
                "content": {
                    "summary_mode": "extractive",
                    "target_words": target_words,
                    "sections": sections,
                    "source_diversity": len({item["evidence_unit_id"] for item in evidence}),
                    "highest_source_tier": min((item["source_tier"] for item in evidence), default="D"),
                },
                "evidence": evidence,
            })
    return units

def serializable_source_quality(value: SourceQuality) -> dict:
    return asdict(value)

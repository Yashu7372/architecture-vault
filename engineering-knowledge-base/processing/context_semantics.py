from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re

from processing.knowledge_enrichment import (
    DuplicateCandidate,
    SourceQuality,
    detect_document_duplicates,
    parse_page_number,
    score_source,
)

SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
SPACE_RE = re.compile(r"\s+")
WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9+.#/_-]*")


@dataclass
class ProcessedDocument:
    document_id: str
    canonical_text: str
    source_quality: SourceQuality


def compact_text(value: str) -> str:
    return SPACE_RE.sub(" ", value or "").strip()


def extractive_gist(value: str, max_chars: int = 360) -> str:
    text = compact_text(value)
    if not text:
        return ""
    sentences = [part.strip() for part in SENTENCE_RE.split(text) if part.strip()]
    chosen: list[str] = []
    length = 0
    for sentence in sentences:
        if chosen and length + 1 + len(sentence) > max_chars:
            break
        chosen.append(sentence)
        length += len(sentence) + (1 if length else 0)
        if len(chosen) >= 3:
            break
    gist = " ".join(chosen) if chosen else text
    if len(gist) > max_chars:
        gist = gist[: max_chars - 1].rstrip() + "…"
    return gist


def _phrase_present(text: str, phrase: str) -> bool:
    value = phrase.strip().lower()
    if not value:
        return False
    # Word-boundary matching for normal terms; substring matching is retained
    # for protocol/version tokens containing punctuation.
    if re.fullmatch(r"[a-z0-9 -]+", value):
        pattern = r"(?<![a-z0-9])" + re.escape(value).replace(r"\ ", r"\s+") + r"(?![a-z0-9])"
        return bool(re.search(pattern, text))
    return value in text


def score_concept(text: str, concept: dict[str, Any]) -> tuple[float, list[str]]:
    lower = compact_text(text).lower()
    if not lower:
        return 0.0, []

    name = str(concept.get("name", "")).strip()
    aliases = [str(value).strip() for value in concept.get("aliases", []) or []]
    keywords = [str(value).strip() for value in concept.get("keywords", []) or []]
    matched: list[str] = []

    primary_terms = [name, *aliases]
    primary_hits = [term for term in primary_terms if term and _phrase_present(lower, term)]
    keyword_hits = [term for term in keywords if term and _phrase_present(lower, term)]
    matched.extend(primary_hits)
    matched.extend(keyword_hits)

    if not matched:
        return 0.0, []

    # Exact concept/alias presence carries the strongest signal. Multiple
    # supporting keywords increase confidence but cannot create authority.
    primary_score = 0.58 if primary_hits else 0.0
    keyword_score = min(0.34, 0.11 * len(set(keyword_hits)))
    support_bonus = 0.08 if primary_hits and keyword_hits else 0.0
    score = min(0.98, primary_score + keyword_score + support_bonus)

    # Keyword-only matches need at least two distinct cues. This prevents a
    # generic word like "cache" or "test" from becoming a concept by itself.
    if not primary_hits and len(set(keyword_hits)) < 2:
        return 0.0, []
    if not primary_hits:
        score = min(0.52, 0.20 + 0.12 * len(set(keyword_hits)))

    return round(score, 4), sorted(set(matched), key=str.lower)


def build_concept_links(
    chunks: list[dict[str, Any]],
    taxonomy: dict[str, Any],
    *,
    min_score: float = 0.28,
) -> list[dict[str, Any]]:
    concepts = taxonomy.get("concepts", []) or []
    links: list[dict[str, Any]] = []
    for chunk in chunks:
        text = f"{chunk.get('title', '')}\n{chunk.get('heading', '')}\n{chunk.get('text', '')}"
        for concept in concepts:
            score, terms = score_concept(text, concept)
            if score < min_score:
                continue
            links.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "document_id": chunk["document_id"],
                    "concept_id": str(concept["id"]),
                    "score": score,
                    "matched_terms": terms,
                    "evidence_state": "EXTRACTED",
                }
            )
    return links


def enrich_documents_and_chunks(
    documents: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    *,
    evidence_policy: dict[str, Any],
) -> tuple[dict[str, SourceQuality], list[DuplicateCandidate], dict[str, str]]:
    chunks_by_document: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunks:
        chunks_by_document.setdefault(chunk["document_id"], []).append(chunk)

    source_scores: dict[str, SourceQuality] = {}
    processed: list[tuple[dict[str, Any], ProcessedDocument]] = []
    for document in documents:
        doc_id = document["document_id"]
        quality = score_source(document, evidence_policy)
        source_scores[doc_id] = quality
        canonical_text = "\n\n".join(
            chunk.get("text", "") for chunk in sorted(chunks_by_document.get(doc_id, []), key=lambda item: item["ordinal"])
        )
        processed.append((document, ProcessedDocument(doc_id, canonical_text, quality)))

    duplicates = detect_document_duplicates(processed)
    representative_by_document = {candidate.document_id: candidate.representative_document_id for candidate in duplicates}
    evidence_unit_by_document = {
        document["document_id"]: representative_by_document.get(document["document_id"], document["document_id"])
        for document in documents
    }

    for chunk in chunks:
        quality = source_scores.get(chunk["document_id"])
        chunk["gist"] = extractive_gist(chunk.get("text", ""))
        chunk["page_number"] = parse_page_number([str(chunk.get("heading", ""))])
        chunk["evidence_unit_id"] = evidence_unit_by_document.get(chunk["document_id"], chunk["document_id"])
        if quality:
            chunk["source_tier"] = quality.tier
            chunk["source_quality_score"] = quality.score
            chunk["authority_type"] = quality.authority

    return source_scores, duplicates, evidence_unit_by_document


def concept_summary(
    taxonomy: dict[str, Any],
    concept_links: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    concept_lookup = {str(concept["id"]): concept for concept in taxonomy.get("concepts", []) or []}
    chunk_lookup = {chunk["chunk_id"]: chunk for chunk in chunks}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for link in concept_links:
        grouped.setdefault(link["concept_id"], []).append(link)

    result: list[dict[str, Any]] = []
    for concept_id, links in sorted(grouped.items()):
        concept = concept_lookup.get(concept_id, {})
        evidence_units = {
            chunk_lookup.get(link["chunk_id"], {}).get("evidence_unit_id") or link["document_id"] for link in links
        }
        result.append(
            {
                "concept_id": concept_id,
                "name": concept.get("name", concept_id),
                "domain": concept.get("domain"),
                "evidence_chunks": len(links),
                "evidence_units": len(evidence_units),
                "max_score": round(max(float(link["score"]) for link in links), 4),
                "evidence_state": "EXTRACTED",
            }
        )
    return result

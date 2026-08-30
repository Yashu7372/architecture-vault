from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import hashlib
import json


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest(value: Any, length: int = 32) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:length]


def _document_key(item: dict[str, Any]) -> str:
    return str(item.get("document_id") or item.get("url") or _digest(item))


def _metadata_fingerprint(item: dict[str, Any]) -> str:
    # Collection time and local note location do not represent source knowledge.
    stable = {
        "title": item.get("title"),
        "url": item.get("url"),
        "source_name": item.get("source_name"),
        "source_type": item.get("source_type"),
        "author": item.get("author"),
        "published_date": item.get("published_date"),
        "tags": sorted(item.get("tags", []) or []),
        "links": sorted(item.get("links", []) or []),
        "metadata": item.get("metadata", {}) or {},
        "capability_id": item.get("capability_id"),
        "trust_boundary": item.get("trust_boundary"),
    }
    return _digest(stable, 64)


def _priority(change_type: str, item: dict[str, Any]) -> tuple[str, float, list[str]]:
    text = " ".join(
        [
            str(item.get("title", "")),
            " ".join(str(tag) for tag in item.get("tags", []) or []),
            str((item.get("metadata", {}) or {}).get("catalog_section", "")),
        ]
    ).lower()
    critical_terms = {
        "api",
        "contract",
        "schema",
        "event",
        "security",
        "authentication",
        "database",
        "dependency",
        "migration",
        "architecture",
        "distributed",
        "reliability",
        "agent",
        "rag",
        "llm",
    }
    hits = sorted(term for term in critical_terms if term in text)
    base = {
        "ADDED": 0.55,
        "CONTENT_CHANGED": 0.82,
        "METADATA_CHANGED": 0.48,
        "REMOVED": 0.75,
    }.get(change_type, 0.4)
    score = min(0.98, base + min(0.14, len(hits) * 0.02))
    if score >= 0.8:
        label = "HIGH"
    elif score >= 0.55:
        label = "MEDIUM"
    else:
        label = "LOW"
    return label, round(score, 3), hits


def evaluate_manifest_delta(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
    *,
    run_id: str,
    successful_sources: set[str] | None = None,
) -> dict[str, Any]:
    """Create deterministic candidate updates for the downstream Knowledge Spine.

    Nothing here promotes canonical knowledge. A delta only says which evidence
    changed and therefore which downstream entities/relations may need targeted
    re-evaluation.
    """

    previous_by_id = {_document_key(item): item for item in previous}
    current_by_id = {_document_key(item): item for item in current}
    changes: list[dict[str, Any]] = []

    for key in sorted(current_by_id.keys() - previous_by_id.keys()):
        item = current_by_id[key]
        priority, score, terms = _priority("ADDED", item)
        changes.append(_change("ADDED", item, None, priority, score, terms))

    for key in sorted(current_by_id.keys() & previous_by_id.keys()):
        before = previous_by_id[key]
        after = current_by_id[key]
        if before.get("content_hash") != after.get("content_hash"):
            priority, score, terms = _priority("CONTENT_CHANGED", after)
            changes.append(_change("CONTENT_CHANGED", after, before, priority, score, terms))
        elif _metadata_fingerprint(before) != _metadata_fingerprint(after):
            priority, score, terms = _priority("METADATA_CHANGED", after)
            changes.append(_change("METADATA_CHANGED", after, before, priority, score, terms))

    allowed_removed_sources = successful_sources
    for key in sorted(previous_by_id.keys() - current_by_id.keys()):
        item = previous_by_id[key]
        if allowed_removed_sources is not None and item.get("source_name") not in allowed_removed_sources:
            continue
        priority, score, terms = _priority("REMOVED", item)
        changes.append(_change("REMOVED", item, item, priority, score, terms))

    changes.sort(key=lambda value: (-float(value["priority_score"]), value["change_type"], value["document_id"]))
    type_counts = Counter(change["change_type"] for change in changes)
    priority_counts = Counter(change["priority"] for change in changes)
    affected_sources = sorted({str(change.get("source_name", "")) for change in changes if change.get("source_name")})

    return {
        "schema_version": 1,
        "run_id": run_id,
        "generated_at": utc_now(),
        "authority": "CANDIDATE_ONLY",
        "promotion_allowed": False,
        "previous_documents": len(previous),
        "current_documents": len(current),
        "change_count": len(changes),
        "change_counts": dict(sorted(type_counts.items())),
        "priority_counts": dict(sorted(priority_counts.items())),
        "affected_sources": affected_sources,
        "changes": changes,
    }


def _change(
    change_type: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
    priority: str,
    priority_score: float,
    matched_terms: list[str],
) -> dict[str, Any]:
    document_id = str(item.get("document_id") or _document_key(item))
    return {
        "delta_id": f"delta-{_digest([change_type, document_id, item.get('content_hash'), _metadata_fingerprint(item)], 20)}",
        "change_type": change_type,
        "document_id": document_id,
        "source_name": item.get("source_name"),
        "source_type": item.get("source_type"),
        "capability_id": item.get("capability_id") or (item.get("metadata", {}) or {}).get("capability_id"),
        "title": item.get("title"),
        "url": item.get("url"),
        "priority": priority,
        "priority_score": priority_score,
        "matched_change_terms": matched_terms,
        "before_content_hash": before.get("content_hash") if before else None,
        "after_content_hash": item.get("content_hash") if change_type != "REMOVED" else None,
        "before_metadata_hash": _metadata_fingerprint(before) if before else None,
        "after_metadata_hash": _metadata_fingerprint(item) if change_type != "REMOVED" else None,
        "required_action": "RE_EVALUATE_KNOWLEDGE" if change_type != "METADATA_CHANGED" else "RE_EVALUATE_METADATA",
        "evidence_state": "OBSERVED_CHANGE",
    }


def write_delta(delta: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    delta_dir = output_dir / "deltas"
    delta_dir.mkdir(parents=True, exist_ok=True)
    run_path = delta_dir / f"{delta['run_id']}.json"
    latest_path = delta_dir / "latest.json"
    payload = json.dumps(delta, indent=2, ensure_ascii=False, sort_keys=True)
    run_path.write_text(payload, encoding="utf-8")
    latest_path.write_text(payload, encoding="utf-8")
    return run_path, latest_path


def build_source_state(
    manifest: list[dict[str, Any]],
    *,
    run_id: str,
    successful_sources: set[str],
    failed_sources: set[str],
) -> dict[str, Any]:
    by_source: dict[str, list[dict[str, Any]]] = {}
    for item in manifest:
        by_source.setdefault(str(item.get("source_name", "unknown")), []).append(item)

    source_state: dict[str, Any] = {}
    for source_name, items in sorted(by_source.items()):
        fingerprints = sorted(
            f"{item.get('document_id')}:{item.get('content_hash')}:{_metadata_fingerprint(item)}" for item in items
        )
        source_state[source_name] = {
            "document_count": len(items),
            "snapshot_hash": _digest(fingerprints, 64),
            "last_run_id": run_id,
            "last_run_status": (
                "PASS" if source_name in successful_sources else "FAIL" if source_name in failed_sources else "UNCHANGED"
            ),
        }
    return {
        "schema_version": 1,
        "updated_at": utc_now(),
        "run_id": run_id,
        "sources": source_state,
    }


def write_source_state(state: dict[str, Any], output_dir: Path) -> Path:
    state_dir = output_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "source-state.json"
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return path

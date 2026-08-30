from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import re

from capabilities.contracts import CapabilityResult, utc_now


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return cleaned or "unknown"


class RunEvidenceStore:
    """Local/private evidence sink for collector executions.

    It intentionally persists only execution metadata and fingerprints; raw
    third-party document bodies are never copied into evidence records.
    """

    def __init__(self, output_dir: Path, run_id: str):
        self.run_id = run_id
        self.root = output_dir / "evidence" / run_id
        self.root.mkdir(parents=True, exist_ok=True)
        self._results: list[dict[str, Any]] = []

    def record(self, result: CapabilityResult) -> Path:
        payload = result.as_dict(include_documents=False)
        source_name = str(result.request.source.get("name", "unknown"))
        filename = f"{_safe_name(result.manifest.capability_id)}--{_safe_name(source_name)}.json"
        path = self.root / filename
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        self._results.append(payload)
        return path

    def finalize(self, extra: dict[str, Any] | None = None) -> Path:
        status_counts: dict[str, int] = {}
        document_count = 0
        flagged = 0
        for result in self._results:
            status = str(result.get("status", "UNKNOWN"))
            status_counts[status] = status_counts.get(status, 0) + 1
            document_count += int(result.get("document_count", 0))
            metrics = result.get("metrics", {}) or {}
            flagged += int(metrics.get("flagged_documents", 0))

        summary: dict[str, Any] = {
            "schema_version": 1,
            "run_id": self.run_id,
            "completed_at": utc_now(),
            "capability_results": len(self._results),
            "status_counts": dict(sorted(status_counts.items())),
            "document_count": document_count,
            "flagged_documents": flagged,
            "results": [
                {
                    "capability_id": result["manifest"]["capability_id"],
                    "source_name": result["request"]["source"].get("name"),
                    "status": result["status"],
                    "document_count": result.get("document_count", 0),
                    "errors": result.get("errors", []),
                    "elapsed_ms": (result.get("metrics", {}) or {}).get("elapsed_ms"),
                }
                for result in self._results
            ],
        }
        if extra:
            summary.update(extra)

        path = self.root / "run-summary.json"
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        return path

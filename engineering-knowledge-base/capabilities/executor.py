from __future__ import annotations

from time import monotonic
from typing import Any

from capabilities.contracts import (
    CapabilityEvidence,
    CapabilityRequest,
    CapabilityResult,
)
from capabilities.registry import CapabilityRegistry
from capabilities.trust import normalize_document


class CapabilityExecutor:
    """Executes one declared collector capability with evidence and isolation.

    This is intentionally not a general agent runtime. It cannot choose another
    capability, mutate destinations, or promote knowledge. It executes the
    capability selected by the source registry and returns typed results.
    """

    def __init__(self, registry: CapabilityRegistry):
        self.registry = registry

    def execute(
        self,
        source: dict[str, Any],
        *,
        run_id: str,
        resume: bool = False,
        dry_run: bool = False,
    ) -> CapabilityResult:
        manifest = self.registry.validate_source(source)
        request = CapabilityRequest(
            capability_id=manifest.capability_id,
            source=self._safe_source_snapshot(source),
            run_id=run_id,
            resume=resume,
            dry_run=dry_run,
        )
        result = CapabilityResult(request=request, manifest=manifest, status="FAIL")
        started = monotonic()
        source_name = str(source["name"])

        try:
            collector = self.registry.create_collector(manifest)
            raw_documents = collector.collect(source)
            normalized = []
            rejected = 0
            for document in raw_documents:
                try:
                    normalized.append(
                        normalize_document(
                            document,
                            capability_id=manifest.capability_id,
                            trust_boundary=manifest.trust_boundary,
                        )
                    )
                except Exception as exc:
                    rejected += 1
                    result.errors.append(f"Rejected document: {exc}")

            flags = sorted(
                {
                    flag
                    for document in normalized
                    for flag in document.metadata.get("untrusted_content_flags", [])
                }
            )
            collector_report = getattr(collector, "last_report", None)
            result.documents = normalized
            result.metrics.update(
                {
                    "raw_documents": len(raw_documents),
                    "normalized_documents": len(normalized),
                    "rejected_documents": rejected,
                    "flagged_documents": sum(
                        1 for document in normalized if document.metadata.get("untrusted_content_flags")
                    ),
                    "flag_reasons": flags,
                    "collector_report": collector_report,
                }
            )
            result.status = "PARTIAL" if result.errors else "PASS"
            if raw_documents and not normalized:
                result.status = "FAIL"

            result.evidence.append(
                CapabilityEvidence.create(
                    evidence_type="COLLECTOR_EXECUTION",
                    capability_id=manifest.capability_id,
                    source_name=source_name,
                    payload={
                        "source_type": source.get("type"),
                        "raw_documents": len(raw_documents),
                        "normalized_documents": len(normalized),
                        "rejected_documents": rejected,
                        "flagged_documents": result.metrics["flagged_documents"],
                        "document_fingerprints": [
                            {
                                "url": document.url,
                                "raw_sha256": document.metadata.get("raw_content_sha256"),
                                "canonical_sha256": document.metadata.get("canonical_content_sha256"),
                            }
                            for document in normalized
                        ],
                    },
                )
            )
        except Exception as exc:
            result.status = "FAIL"
            result.errors.append(f"{type(exc).__name__}: {exc}")
            result.evidence.append(
                CapabilityEvidence.create(
                    evidence_type="COLLECTOR_FAILURE",
                    capability_id=manifest.capability_id,
                    source_name=source_name,
                    payload={"source_type": source.get("type"), "error": result.errors[-1]},
                )
            )
        finally:
            elapsed_ms = round((monotonic() - started) * 1000, 2)
            result.metrics["elapsed_ms"] = elapsed_ms
            result.metrics["declared_timeout_seconds"] = manifest.timeout_seconds
            if elapsed_ms > manifest.timeout_seconds * 1000:
                result.metrics["timeout_budget_exceeded"] = True
            result.finish()

        return result

    @staticmethod
    def _safe_source_snapshot(source: dict[str, Any]) -> dict[str, Any]:
        """Keep config evidence without copying credentials/session locations."""
        redacted_keys = {
            "password",
            "token",
            "api_key",
            "secret",
            "cookie",
            "cookies",
            "authorization",
            "user_data_dir",
        }
        snapshot: dict[str, Any] = {}
        for key, value in source.items():
            if key.lower() in redacted_keys:
                snapshot[key] = "[REDACTED]"
            else:
                snapshot[key] = value
        return snapshot

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import hashlib
import json
import uuid


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_digest(value: Any, length: int = 24) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:length]


@dataclass(frozen=True)
class CapabilityManifest:
    """Machine-readable declaration of a bounded Enterprise OS capability."""

    capability_id: str
    version: str
    kind: str
    entrypoint: str
    source_types: tuple[str, ...]
    description: str = ""
    deterministic: bool = True
    network_access: bool = False
    external_writes: bool = False
    local_writes: bool = False
    auth_mode: str = "none"
    trust_boundary: str = "UNTRUSTED_EXTERNAL"
    timeout_seconds: int = 120
    output_contract: str = "KnowledgeDocument[]"
    tags: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "CapabilityManifest":
        side_effects = value.get("side_effects", {}) or {}
        return cls(
            capability_id=str(value["id"]),
            version=str(value.get("version", "1")),
            kind=str(value.get("kind", "collector")),
            entrypoint=str(value["entrypoint"]),
            source_types=tuple(str(item) for item in value.get("source_types", [])),
            description=str(value.get("description", "")),
            deterministic=bool(value.get("deterministic", True)),
            network_access=bool(value.get("network_access", False)),
            external_writes=bool(side_effects.get("external_writes", False)),
            local_writes=bool(side_effects.get("local_writes", False)),
            auth_mode=str(value.get("auth_mode", "none")),
            trust_boundary=str(value.get("trust_boundary", "UNTRUSTED_EXTERNAL")),
            timeout_seconds=int(value.get("timeout_seconds", 120)),
            output_contract=str(value.get("output_contract", "KnowledgeDocument[]")),
            tags=tuple(str(item) for item in value.get("tags", [])),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapabilityRequest:
    capability_id: str
    source: dict[str, Any]
    run_id: str = field(default_factory=lambda: f"run-{uuid.uuid4().hex[:16]}")
    request_id: str = field(default_factory=lambda: f"req-{uuid.uuid4().hex[:16]}")
    requested_at: str = field(default_factory=utc_now)
    resume: bool = False
    dry_run: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapabilityEvidence:
    evidence_id: str
    evidence_type: str
    capability_id: str
    source_name: str
    captured_at: str
    payload: dict[str, Any]
    payload_hash: str

    @classmethod
    def create(
        cls,
        *,
        evidence_type: str,
        capability_id: str,
        source_name: str,
        payload: dict[str, Any],
    ) -> "CapabilityEvidence":
        payload_hash = stable_digest(payload, 64)
        return cls(
            evidence_id=f"evidence-{stable_digest([capability_id, source_name, evidence_type, payload_hash], 20)}",
            evidence_type=evidence_type,
            capability_id=capability_id,
            source_name=source_name,
            captured_at=utc_now(),
            payload=payload,
            payload_hash=payload_hash,
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CapabilityResult:
    request: CapabilityRequest
    manifest: CapabilityManifest
    status: str
    documents: list[Any] = field(default_factory=list)
    evidence: list[CapabilityEvidence] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=utc_now)
    completed_at: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "PASS"

    def finish(self) -> None:
        self.completed_at = utc_now()

    def as_dict(self, include_documents: bool = False) -> dict[str, Any]:
        payload = {
            "request": self.request.as_dict(),
            "manifest": self.manifest.as_dict(),
            "status": self.status,
            "evidence": [item.as_dict() for item in self.evidence],
            "errors": list(self.errors),
            "metrics": dict(self.metrics),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
        if include_documents:
            payload["documents"] = [asdict(item) if hasattr(item, "__dataclass_fields__") else item for item in self.documents]
        else:
            payload["document_count"] = len(self.documents)
        return payload

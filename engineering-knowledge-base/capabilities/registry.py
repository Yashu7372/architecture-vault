from __future__ import annotations

from pathlib import Path
from typing import Any
import importlib

import yaml

from capabilities.contracts import CapabilityManifest
from collectors.base import BaseCollector


class CapabilityRegistry:
    """Loads collector capability manifests without coupling the OS to classes."""

    def __init__(self, manifests: list[CapabilityManifest]):
        self._by_id: dict[str, CapabilityManifest] = {}
        self._by_source_type: dict[str, CapabilityManifest] = {}
        for manifest in manifests:
            if manifest.capability_id in self._by_id:
                raise ValueError(f"Duplicate capability id: {manifest.capability_id}")
            if manifest.kind != "collector":
                raise ValueError(f"Architecture Vault registry only accepts collector capabilities: {manifest.capability_id}")
            if manifest.external_writes:
                raise ValueError(
                    f"Collector capability {manifest.capability_id} declares external writes. "
                    "Collectors must be acquisition-only; persistence is owned by the Vault pipeline."
                )
            if not manifest.source_types:
                raise ValueError(f"Capability {manifest.capability_id} has no source_types")
            if manifest.timeout_seconds <= 0:
                raise ValueError(f"Capability {manifest.capability_id} timeout_seconds must be positive")
            self._by_id[manifest.capability_id] = manifest
            for source_type in manifest.source_types:
                if source_type in self._by_source_type:
                    other = self._by_source_type[source_type]
                    raise ValueError(
                        f"Source type '{source_type}' is claimed by both "
                        f"{other.capability_id} and {manifest.capability_id}"
                    )
                self._by_source_type[source_type] = manifest

    @classmethod
    def from_file(cls, path: Path) -> "CapabilityRegistry":
        if not path.is_file():
            raise FileNotFoundError(f"Missing capability registry: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if int(data.get("version", 0)) < 1:
            raise ValueError("Capability registry version must be >= 1")
        raw = data.get("capabilities", [])
        if not isinstance(raw, list) or not raw:
            raise ValueError("Capability registry must contain a non-empty capabilities list")
        return cls([CapabilityManifest.from_dict(item) for item in raw])

    @classmethod
    def default(cls, root: Path) -> "CapabilityRegistry":
        return cls.from_file(root / "config" / "capabilities.yaml")

    def manifests(self) -> list[CapabilityManifest]:
        return sorted(self._by_id.values(), key=lambda item: item.capability_id)

    def for_source_type(self, source_type: str) -> CapabilityManifest:
        try:
            return self._by_source_type[source_type]
        except KeyError as exc:
            known = ", ".join(sorted(self._by_source_type))
            raise ValueError(f"Unsupported source type '{source_type}'. Registered: {known}") from exc

    def get(self, capability_id: str) -> CapabilityManifest:
        try:
            return self._by_id[capability_id]
        except KeyError as exc:
            raise ValueError(f"Unknown capability id: {capability_id}") from exc

    def create_collector(self, manifest: CapabilityManifest) -> BaseCollector:
        module_name, separator, class_name = manifest.entrypoint.partition(":")
        if not separator or not module_name or not class_name:
            raise ValueError(
                f"Invalid entrypoint '{manifest.entrypoint}' for {manifest.capability_id}; "
                "expected module.path:ClassName"
            )
        module = importlib.import_module(module_name)
        collector_type: Any = getattr(module, class_name, None)
        if collector_type is None:
            raise ValueError(f"Entrypoint class not found: {manifest.entrypoint}")
        collector = collector_type()
        if not isinstance(collector, BaseCollector):
            raise TypeError(f"Entrypoint {manifest.entrypoint} is not a BaseCollector")
        return collector

    def validate_source(self, source: dict[str, Any]) -> CapabilityManifest:
        name = str(source.get("name", "")).strip()
        source_type = str(source.get("type", "")).strip()
        if not name:
            raise ValueError("Source is missing name")
        if not source_type:
            raise ValueError(f"Source '{name}' is missing type")
        manifest = self.for_source_type(source_type)
        if source.get("login_required") and manifest.auth_mode == "none":
            raise ValueError(
                f"Source '{name}' requires login but capability {manifest.capability_id} does not declare auth support"
            )
        return manifest

    def validate_all_sources(self, sources: list[dict[str, Any]]) -> list[str]:
        errors: list[str] = []
        seen: set[str] = set()
        for source in sources:
            name = str(source.get("name", "")).strip()
            if name in seen:
                errors.append(f"Duplicate source name: {name}")
            seen.add(name)
            try:
                self.validate_source(source)
            except Exception as exc:
                errors.append(str(exc))
        return errors

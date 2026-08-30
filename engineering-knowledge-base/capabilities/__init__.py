"""Portable capability contracts for Architecture Vault.

The Enterprise OS control plane owns scheduling, authorization and cross-project
execution. Architecture Vault only implements bounded capabilities and exposes
machine-readable manifests that the control plane can discover later.
"""

from capabilities.contracts import (
    CapabilityEvidence,
    CapabilityManifest,
    CapabilityRequest,
    CapabilityResult,
)
from capabilities.executor import CapabilityExecutor
from capabilities.registry import CapabilityRegistry

__all__ = [
    "CapabilityEvidence",
    "CapabilityExecutor",
    "CapabilityManifest",
    "CapabilityRegistry",
    "CapabilityRequest",
    "CapabilityResult",
]

from __future__ import annotations

from dataclasses import replace
from typing import Iterable
from urllib.parse import urlparse, urlunparse
import hashlib
import re

from collectors.base import KnowledgeDocument

# External article/repository text is evidence, never an instruction. These
# patterns are warnings for review and context-pack policy; they are not the
# security boundary. Authority remains in capability/pipeline controls.
INVISIBLE_RE = re.compile(
    r"[\u00AD\u034F\u200B-\u200F\u202A-\u202E\u2060-\u2064\u2066-\u206F\uFEFF]|[\U000E0000-\U000E007F]"
)
CONTROL_RE = re.compile(r"[\x00-\x08\x0B-\x1F\x7F-\x9F]")
INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction-override",
        re.compile(
            r"\b(ignore|disregard|forget)\b[^.\n]{0,60}\b(previous|prior|above|earlier|all)\b"
            r"[^.\n]{0,30}\b(instruction|prompt|rule|context)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "role-hijack",
        re.compile(r"\b(you are now|act as|pretend to be|new persona|system prompt)\b", re.IGNORECASE),
    ),
    (
        "tool-directive",
        re.compile(r"(tool_call|function_call|<\s*tool\b|call the [^.\n]{0,30}tool)", re.IGNORECASE),
    ),
    (
        "credential-probe",
        re.compile(
            r"\b(your|my|the)\s+(api[_\s-]?key|secret key|password|access token|credentials?)\b|\.env\b",
            re.IGNORECASE,
        ),
    ),
    (
        "exfiltration-shape",
        re.compile(
            r"\b(send|post|upload|forward|email|exfiltrate|leak)\b[^.\n]{0,70}"
            r"\b(to|at)\b[^.\n]{0,30}(https?://|www\.|@)",
            re.IGNORECASE,
        ),
    ),
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def clean_text(value: str, max_chars: int | None = None) -> str:
    cleaned = INVISIBLE_RE.sub("", value or "")
    cleaned = CONTROL_RE.sub(" ", cleaned)
    if max_chars is not None and len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + "…[truncated]"
    return cleaned.strip()


def inspect_untrusted(value: str) -> list[str]:
    text = clean_text(value)
    return [name for name, pattern in INJECTION_PATTERNS if pattern.search(text)]


def safe_url(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlparse(raw)
    except Exception:
        return ""
    if parsed.scheme not in {"http", "https", "file", ""}:
        return ""
    if parsed.username or parsed.password:
        return ""
    if parsed.scheme in {"http", "https"} and not parsed.netloc:
        return ""
    return urlunparse(parsed)


def _clean_tags(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        tag = clean_text(str(value), 120).strip()
        if tag and tag not in seen:
            seen.add(tag)
            result.append(tag)
    return result


def normalize_document(
    document: KnowledgeDocument,
    *,
    capability_id: str,
    trust_boundary: str,
) -> KnowledgeDocument:
    raw_content = document.content or ""
    canonical_content = clean_text(raw_content)
    title = clean_text(document.title, 500) or "Untitled"
    author = clean_text(document.author or "", 300) or None
    url = safe_url(document.url)
    if not url:
        raise ValueError(f"Collector returned unsafe or invalid URL for '{title}'")

    flags = sorted(set(inspect_untrusted(f"{title}\n{canonical_content[:12000]}")))
    metadata = dict(document.metadata or {})
    metadata.update(
        {
            "capability_id": capability_id,
            "trust_boundary": trust_boundary,
            "raw_content_sha256": sha256_text(raw_content),
            "canonical_content_sha256": sha256_text(canonical_content),
            "untrusted_content_flags": flags,
            "content_role": "data-not-instructions",
        }
    )

    return replace(
        document,
        title=title,
        url=url,
        content=canonical_content,
        author=author,
        tags=_clean_tags(document.tags),
        links=[safe for safe in (safe_url(link) for link in document.links) if safe],
        metadata=metadata,
    )

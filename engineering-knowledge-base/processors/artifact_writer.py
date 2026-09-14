from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import hashlib
import json

from slugify import slugify

from collectors.base import KnowledgeDocument


class ArtifactWriter:
    def __init__(self, root: Path):
        self.root = root
        self.raw_dir = root / "output" / "raw"
        self.packet_dir = root / "output" / "analysis-packets"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.packet_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def source_id(url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

    def write_raw(self, doc: KnowledgeDocument) -> Path:
        source_id = self.source_id(doc.url)
        filename = f"{source_id}-{slugify(doc.title)[:80]}.md"
        path = self.raw_dir / filename
        metadata = {
            "source_id": source_id,
            "title": doc.title,
            "url": doc.url,
            "source_name": doc.source_name,
            "source_type": doc.source_type,
            "author": doc.author,
            "published_date": doc.published_date,
            "tags": doc.tags,
            "links": doc.links,
        }
        content = (
            "---\n"
            + "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in metadata.items())
            + "\n---\n\n"
            + "# Raw Source Evidence\n\n"
            + doc.content.strip()
            + "\n"
        )
        path.write_text(content, encoding="utf-8")
        return path

    def write_analysis_packet(self, doc: KnowledgeDocument, raw_path: Path) -> Path:
        source_id = self.source_id(doc.url)
        packet = {
            "schema_version": "1.0",
            "source_id": source_id,
            "source": {
                "title": doc.title,
                "url": doc.url,
                "source_name": doc.source_name,
                "source_type": doc.source_type,
                "author": doc.author,
                "published_date": doc.published_date,
                "tags": doc.tags,
                "raw_file": str(raw_path.relative_to(self.root)),
            },
            "requested_outputs": {
                "ten_minute_digest": True,
                "concepts": True,
                "patterns": True,
                "anti_patterns": True,
                "tradeoffs": True,
                "production_concerns": True,
                "evidence_claims": True,
                "relationships": True,
                "project_relevance": True,
            },
            "status": "READY_FOR_AI_ANALYSIS",
        }
        path = self.packet_dir / f"{source_id}.json"
        path.write_text(json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

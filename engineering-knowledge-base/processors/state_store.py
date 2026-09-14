from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import json


class StateStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {"schema_version": "1.0", "items": {}}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"schema_version": "1.0", "items": {}}

    def get(self, source_id: str) -> dict | None:
        return self.data["items"].get(source_id)

    def should_process(self, source_id: str, retry_failed: bool = False) -> bool:
        item = self.get(source_id)
        if not item:
            return True
        if item.get("status") == "FAILED":
            return retry_failed
        return item.get("status") not in {"EXTRACTED", "READY_FOR_AI_ANALYSIS", "ANALYZED", "ACCEPTED"}

    def mark(self, source_id: str, url: str, status: str, **extra) -> None:
        item = self.data["items"].setdefault(source_id, {"url": url, "attempts": 0})
        if status == "PROCESSING":
            item["attempts"] = int(item.get("attempts", 0)) + 1
        item.update(extra)
        item["url"] = url
        item["status"] = status
        item["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

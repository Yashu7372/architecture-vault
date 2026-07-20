from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class KnowledgeDocument:
    title: str
    url: str
    source_name: str
    source_type: str
    content: str
    author: Optional[str] = None
    published_date: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseCollector:
    def collect(self, source: dict) -> list[KnowledgeDocument]:
        raise NotImplementedError("Collector must implement collect(source)")

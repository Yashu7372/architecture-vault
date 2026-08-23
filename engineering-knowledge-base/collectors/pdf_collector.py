from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import requests
from pypdf import PdfReader

from collectors.base import BaseCollector, KnowledgeDocument


class PdfCollector(BaseCollector):
    def collect(self, source: dict) -> list[KnowledgeDocument]:
        source_value = source.get("path") or source.get("url") or ""
        if source_value.startswith(("http://", "https://")):
            response = requests.get(source_value, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
            response.raise_for_status()
            reader = PdfReader(BytesIO(response.content))
            document_title = Path(urlparse(source_value).path).stem or source.get("name", "PDF")
            document_url = source_value
        else:
            pdf_path = Path(source_value)
            if not pdf_path.exists():
                print(f"PDF not found: {pdf_path}")
                return []
            reader = PdfReader(str(pdf_path))
            document_title = pdf_path.stem
            document_url = str(pdf_path)

        sections = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            sections.append(f"\n\n## Page {page_number}\n\n{text}")

        return [
            KnowledgeDocument(
                title=document_title.replace("_", " ").replace("-", " ").title(),
                url=document_url,
                source_name=source["name"],
                source_type="pdf",
                content="\n".join(sections),
                tags=source.get("tags", []),
            )
        ]

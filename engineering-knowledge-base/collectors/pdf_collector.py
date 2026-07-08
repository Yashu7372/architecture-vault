from pathlib import Path
from pypdf import PdfReader

from collectors.base import BaseCollector, KnowledgeDocument


class PdfCollector(BaseCollector):
    def collect(self, source: dict) -> list[KnowledgeDocument]:
        source_path = source.get("path") or source.get("url") or ""
        pdf_path = Path(source_path)
        if not pdf_path.exists():
            print(f"PDF not found: {pdf_path}")
            return []

        reader = PdfReader(str(pdf_path))
        sections = []
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            sections.append(f"\n\n## Page {page_number}\n\n{text}")

        document_title = pdf_path.stem.replace("_", " ").replace("-", " ").title()
        return [
            KnowledgeDocument(
                title=document_title,
                url=str(pdf_path),
                source_name=source["name"],
                source_type="pdf",
                content="\n".join(sections),
                tags=source.get("tags", []),
            )
        ]

from __future__ import annotations

from io import BytesIO

import fitz
from docx import Document


class FileExtractionService:
    ALLOWED_EXTENSIONS = {".pdf", ".docx"}

    def extract_text(self, filename: str, content: bytes) -> str:
        lower_name = filename.lower()

        if lower_name.endswith(".pdf"):
            return self._extract_pdf_text(content)

        if lower_name.endswith(".docx"):
            return self._extract_docx_text(content)

        raise ValueError("Unsupported resume format")

    def _extract_pdf_text(self, content: bytes) -> str:
        document = fitz.open(stream=content, filetype="pdf")
        pages = [page.get_text("text") for page in document]
        return "\n".join(page.strip() for page in pages if page.strip()).strip()

    def _extract_docx_text(self, content: bytes) -> str:
        document = Document(BytesIO(content))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        return "\n".join(paragraphs).strip()

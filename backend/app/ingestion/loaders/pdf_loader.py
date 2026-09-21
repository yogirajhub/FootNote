from .base import DocumentLoader, LoadedDocument, DocumentPage
from typing import List
import structlog

logger = structlog.get_logger()


class PDFLoader(DocumentLoader):
    """Load PDF files using pypdf."""

    def supported_extensions(self) -> List[str]:
        return ["pdf"]

    def load(self, file_path: str) -> LoadedDocument:
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError("pypdf is required: pip install pypdf")

        logger.info("Loading PDF", path=file_path)
        reader = PdfReader(file_path)
        pages: List[DocumentPage] = []

        raw_meta = {}
        if reader.metadata:
            raw_meta = {
                "title": reader.metadata.get("/Title", ""),
                "author": reader.metadata.get("/Author", ""),
                "subject": reader.metadata.get("/Subject", ""),
                "creator": reader.metadata.get("/Creator", ""),
            }

        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                pages.append(DocumentPage(
                    content=text,
                    page_number=i + 1,
                    metadata={"page": i + 1},
                ))

        logger.info("PDF loaded", pages=len(pages))
        return LoadedDocument(
            pages=pages,
            total_pages=len(reader.pages),
            format="pdf",
            raw_metadata=raw_meta,
        )

import os
from concurrent.futures import ThreadPoolExecutor
from .base import DocumentLoader, LoadedDocument, DocumentPage
from typing import List
import structlog

logger = structlog.get_logger()


class PDFLoader(DocumentLoader):
    """Load PDF files using pypdf with parallel multi-threaded extraction."""

    def supported_extensions(self) -> List[str]:
        return ["pdf"]

    def load(self, file_path: str) -> LoadedDocument:
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError("pypdf is required: pip install pypdf")

        logger.info("Loading PDF", path=file_path)
        reader = PdfReader(file_path)
        total_pages = len(reader.pages)

        raw_meta = {}
        if reader.metadata:
            raw_meta = {
                "title": reader.metadata.get("/Title", ""),
                "author": reader.metadata.get("/Author", ""),
                "subject": reader.metadata.get("/Subject", ""),
                "creator": reader.metadata.get("/Creator", ""),
            }

        def _extract_page(idx: int) -> DocumentPage:
            try:
                page = reader.pages[idx]
                text = page.extract_text() or ""
                text = text.replace("\x00", "").replace("\r\n", "\n").strip()
            except Exception as e:
                logger.warning("Failed extracting page", page=idx + 1, error=str(e))
                text = ""
            return DocumentPage(
                content=text,
                page_number=idx + 1,
                metadata={"page": idx + 1},
            )

        # Parallel extraction for documents with multiple pages
        if total_pages > 4:
            max_workers = min(8, max(2, os.cpu_count() or 4))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                pages = list(executor.map(_extract_page, range(total_pages)))
        else:
            pages = [_extract_page(i) for i in range(total_pages)]

        logger.info("PDF loaded", pages=len(pages))
        return LoadedDocument(
            pages=pages,
            total_pages=total_pages,
            format="pdf",
            raw_metadata=raw_meta,
        )

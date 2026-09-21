from .base import DocumentLoader, LoadedDocument, DocumentPage
from typing import List
import structlog

logger = structlog.get_logger()


class TXTLoader(DocumentLoader):
    """Load plain text files."""

    def supported_extensions(self) -> List[str]:
        return ["txt"]

    def load(self, file_path: str) -> LoadedDocument:
        logger.info("Loading TXT", path=file_path)

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Split into logical pages by double newlines (paragraphs)
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        page_size = 30
        pages: List[DocumentPage] = []

        for i in range(0, len(paragraphs), page_size):
            chunk = paragraphs[i: i + page_size]
            page_num = i // page_size + 1
            pages.append(DocumentPage(
                content="\n\n".join(chunk),
                page_number=page_num,
                metadata={"page": page_num},
            ))

        if not pages:
            pages = [DocumentPage(content=content, page_number=1, metadata={"page": 1})]

        logger.info("TXT loaded", pages=len(pages))
        return LoadedDocument(
            pages=pages,
            total_pages=len(pages),
            format="txt",
            raw_metadata={},
        )

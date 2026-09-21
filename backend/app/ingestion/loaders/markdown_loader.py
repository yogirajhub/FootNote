from .base import DocumentLoader, LoadedDocument, DocumentPage
from typing import List
import re
import structlog

logger = structlog.get_logger()


class MarkdownLoader(DocumentLoader):
    """Load Markdown files, preserving heading structure."""

    def supported_extensions(self) -> List[str]:
        return ["md", "markdown"]

    def load(self, file_path: str) -> LoadedDocument:
        logger.info("Loading Markdown", path=file_path)

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Split by headings to create logical sections as pages
        sections = re.split(r"(?m)^(#{1,6}\s+.+)$", content)
        pages: List[DocumentPage] = []
        page_num = 1

        current_heading = ""
        buffer = []

        for part in sections:
            if re.match(r"^#{1,6}\s+", part):
                # flush previous buffer
                if buffer:
                    page_text = current_heading + "\n\n" + "\n".join(buffer) if current_heading else "\n".join(buffer)
                    if page_text.strip():
                        pages.append(DocumentPage(
                            content=page_text.strip(),
                            page_number=page_num,
                            metadata={"page": page_num, "heading": current_heading},
                        ))
                        page_num += 1
                current_heading = part.strip()
                buffer = []
            else:
                stripped = part.strip()
                if stripped:
                    buffer.append(stripped)

        # flush last
        if buffer or current_heading:
            page_text = current_heading + "\n\n" + "\n".join(buffer) if current_heading else "\n".join(buffer)
            if page_text.strip():
                pages.append(DocumentPage(
                    content=page_text.strip(),
                    page_number=page_num,
                    metadata={"page": page_num, "heading": current_heading},
                ))

        if not pages:
            pages = [DocumentPage(content=content, page_number=1, metadata={"page": 1})]

        logger.info("Markdown loaded", pages=len(pages))
        return LoadedDocument(
            pages=pages,
            total_pages=len(pages),
            format="md",
            raw_metadata={},
        )

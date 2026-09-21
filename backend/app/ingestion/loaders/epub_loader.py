from .base import DocumentLoader, LoadedDocument, DocumentPage
from typing import List
import structlog

logger = structlog.get_logger()


class EPUBLoader(DocumentLoader):
    """Load EPUB files using ebooklib + BeautifulSoup."""

    def supported_extensions(self) -> List[str]:
        return ["epub"]

    def load(self, file_path: str) -> LoadedDocument:
        try:
            import ebooklib
            from ebooklib import epub
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError("ebooklib and beautifulsoup4 are required")

        logger.info("Loading EPUB", path=file_path)

        book = epub.read_epub(file_path, options={"ignore_ncx": True})
        pages: List[DocumentPage] = []
        page_num = 1

        raw_meta = {
            "title": book.get_metadata("DC", "title")[0][0] if book.get_metadata("DC", "title") else "",
            "author": book.get_metadata("DC", "creator")[0][0] if book.get_metadata("DC", "creator") else "",
        }

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                html_content = item.get_content().decode("utf-8", errors="replace")
                soup = BeautifulSoup(html_content, "lxml")

                # Remove scripts and styles
                for tag in soup(["script", "style", "nav"]):
                    tag.decompose()

                text = soup.get_text(separator="\n", strip=True)
                text = "\n".join(line for line in text.splitlines() if line.strip())

                if len(text) > 100:  # skip near-empty items
                    pages.append(DocumentPage(
                        content=text,
                        page_number=page_num,
                        metadata={"page": page_num, "epub_item": item.get_name()},
                    ))
                    page_num += 1

        if not pages:
            raise ValueError("No readable content found in EPUB")

        logger.info("EPUB loaded", pages=len(pages))
        return LoadedDocument(
            pages=pages,
            total_pages=len(pages),
            format="epub",
            raw_metadata=raw_meta,
        )

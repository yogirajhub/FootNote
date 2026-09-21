"""
Document parser — selects the correct loader and returns a LoadedDocument.
"""
import os
from app.ingestion.loaders import (
    DocumentLoader, LoadedDocument,
    PDFLoader, DOCXLoader, TXTLoader, MarkdownLoader, EPUBLoader,
)
import structlog

logger = structlog.get_logger()

_LOADERS: list[DocumentLoader] = [
    PDFLoader(),
    DOCXLoader(),
    TXTLoader(),
    MarkdownLoader(),
    EPUBLoader(),
]


def get_loader(file_path: str) -> DocumentLoader:
    ext = os.path.splitext(file_path)[1].lstrip(".").lower()
    for loader in _LOADERS:
        if loader.can_load(ext):
            return loader
    raise ValueError(f"Unsupported file format: .{ext}")


def parse_document(file_path: str) -> LoadedDocument:
    """Parse a document file and return a LoadedDocument."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    loader = get_loader(file_path)
    logger.info("Parsing document", file=file_path, loader=type(loader).__name__)
    return loader.load(file_path)


def supported_formats() -> list[str]:
    exts = []
    for loader in _LOADERS:
        exts.extend(loader.supported_extensions())
    return exts

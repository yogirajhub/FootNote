"""
Structure detector — detects document hierarchy (parts, chapters, sections)
from raw text pages. Works for books, research papers, documentation, etc.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from app.ingestion.loaders.base import LoadedDocument, DocumentPage
import structlog

logger = structlog.get_logger()


@dataclass
class DocumentSection:
    """A structural node in the document hierarchy."""
    title: str
    level: int          # 1=top, 2=chapter/section, 3=subsection, etc.
    page_number: Optional[int] = None
    content_start_page: Optional[int] = None
    content_end_page: Optional[int] = None
    parent_title: Optional[str] = None
    order: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectedStructure:
    sections: List[DocumentSection]
    document_type_hint: str   # book, research_paper, documentation, other
    has_chapters: bool
    has_parts: bool


# ── Heading patterns ───────────────────────────────────────────────────────────

_PART_PATTERN = re.compile(
    r"^(?:part|volume|book)\s+(?:[ivxlcdm]+|\d+)[:\.\s]",
    re.IGNORECASE,
)
_CHAPTER_PATTERN = re.compile(
    r"^(?:chapter|ch\.?)\s+(?:\d+|[ivxlcdm]+)[:\.\s]?",
    re.IGNORECASE,
)
_SECTION_PATTERNS = [
    re.compile(r"^(\d+)\.\s+[A-Z]"),          # 1. Introduction
    re.compile(r"^(\d+\.\d+)\s+[A-Z]"),       # 1.1 Background
    re.compile(r"^[A-Z][A-Z\s]{3,}$"),        # ALL CAPS HEADING
    re.compile(r"^#{1,4}\s+"),                 # Markdown headings
]
_RESEARCH_SECTIONS = re.compile(
    r"^(abstract|introduction|background|methodology|methods?|results?|discussion|conclusion|references?|acknowledgements?|appendix)\b",
    re.IGNORECASE,
)


def detect_structure(doc: LoadedDocument) -> DetectedStructure:
    """Detect hierarchical structure from a loaded document."""
    sections: List[DocumentSection] = []
    has_chapters = False
    has_parts = False
    order = 0

    from collections import Counter
    title_counts = Counter()

    for page in doc.pages:
        lines = page.content.splitlines()
        for line in lines[:15]:  # check first 15 lines of each page for headings
            line = line.strip()
            
            # Drop pure digits, short lines, or excessively long lines
            if not line or len(line) < 4 or len(line) > 200 or line.isdigit():
                continue

            section = None
            if _PART_PATTERN.match(line):
                has_parts = True
                section = DocumentSection(title=line, level=1, page_number=page.page_number, order=order)
            elif _CHAPTER_PATTERN.match(line):
                has_chapters = True
                section = DocumentSection(title=line, level=2, page_number=page.page_number, order=order)
            elif _RESEARCH_SECTIONS.match(line) and len(line) < 60:
                section = DocumentSection(title=line, level=2, page_number=page.page_number, order=order)
            else:
                for pat in _SECTION_PATTERNS:
                    if pat.match(line) and len(line) < 120:
                        section = DocumentSection(title=line, level=3, page_number=page.page_number, order=order)
                        break
            
            if section:
                sections.append(section)
                title_counts[line] += 1
                order += 1

    # Filter running headers (appearing > 5 times or on > 25% of pages)
    page_threshold = max(2, int(doc.total_pages * 0.25))
    filtered_sections = []
    
    # Re-order logic since we drop some items
    new_order = 0
    for sec in sections:
        if title_counts[sec.title] > 5 or title_counts[sec.title] > page_threshold:
            continue
        sec.order = new_order
        filtered_sections.append(sec)
        new_order += 1
        
    sections = filtered_sections

    # Determine document type hint
    doc_type_hint = _guess_document_type(sections, doc)

    # Set parent relationships
    _assign_parents(sections)

    logger.info(
        "Structure detected",
        sections=len(sections),
        has_chapters=has_chapters,
        has_parts=has_parts,
        doc_type=doc_type_hint,
    )

    return DetectedStructure(
        sections=sections,
        document_type_hint=doc_type_hint,
        has_chapters=has_chapters,
        has_parts=has_parts,
    )


def _guess_document_type(sections: List[DocumentSection], doc: LoadedDocument) -> str:
    has_abstract = any(_RESEARCH_SECTIONS.match(s.title) for s in sections)
    has_chapters = any(_CHAPTER_PATTERN.match(s.title) for s in sections)

    if has_abstract:
        return "research_paper"
    if has_chapters:
        return "book"
    if doc.total_pages > 100:
        return "book"
    return "other"


def _assign_parents(sections: List[DocumentSection]) -> None:
    """Set parent_title on each section based on level hierarchy."""
    stack: List[DocumentSection] = []
    for sec in sections:
        while stack and stack[-1].level >= sec.level:
            stack.pop()
        if stack:
            sec.parent_title = stack[-1].title
        stack.append(sec)

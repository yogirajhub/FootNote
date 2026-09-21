"""
Tests for structure-aware chunker.
"""
import pytest
from app.ingestion.loaders.base import LoadedDocument, DocumentPage
from app.ingestion.structure_detector import DetectedStructure, DocumentSection
from app.ingestion.chunker import chunk_document, _estimate_tokens


def make_loaded_doc(pages_content: list[str]) -> LoadedDocument:
    pages = [
        DocumentPage(content=text, page_number=i + 1, metadata={"page": i + 1})
        for i, text in enumerate(pages_content)
    ]
    return LoadedDocument(pages=pages, total_pages=len(pages), format="txt")


def make_empty_structure() -> DetectedStructure:
    return DetectedStructure(
        sections=[], document_type_hint="other", has_chapters=False, has_parts=False
    )


def test_basic_chunking():
    doc = make_loaded_doc(["Hello world. This is a test paragraph.\n\nSecond paragraph here."])
    structure = make_empty_structure()
    chunks = chunk_document(doc, structure, "doc_test", "v_001")
    assert len(chunks) >= 1
    assert all(c.content.strip() for c in chunks)


def test_chunk_has_metadata():
    doc = make_loaded_doc(["Sample content for metadata test."])
    structure = make_empty_structure()
    chunks = chunk_document(doc, structure, "doc_test", "v_001")
    assert chunks
    c = chunks[0]
    assert c.metadata["document_id"] == "doc_test"
    assert c.metadata["document_version_id"] == "v_001"
    assert c.metadata["page"] == 1


def test_chunk_linking():
    """Verify previous_chunk_id / next_chunk_id links are correct."""
    long_text = " ".join(["word"] * 1000)
    doc = make_loaded_doc([long_text])
    structure = make_empty_structure()
    chunks = chunk_document(doc, structure, "doc_test", "v_001", chunk_size=100)

    for i, chunk in enumerate(chunks):
        if i > 0:
            assert chunk.previous_chunk_id == chunks[i - 1].chunk_id
        if i < len(chunks) - 1:
            assert chunk.next_chunk_id == chunks[i + 1].chunk_id


def test_section_metadata_attached():
    """Chunks should include chapter/section metadata from structure."""
    doc = make_loaded_doc(["Content of chapter one.", "Content of section two."])
    section = DocumentSection(title="Chapter 1: Introduction", level=2, page_number=1, order=0)
    structure = DetectedStructure(
        sections=[section],
        document_type_hint="book",
        has_chapters=True,
        has_parts=False,
    )
    chunks = chunk_document(doc, structure, "doc_test", "v_001")
    assert any("chapter" in c.metadata for c in chunks)


def test_estimate_tokens():
    assert _estimate_tokens("hello") >= 1
    assert _estimate_tokens("a" * 400) == 100


def test_empty_document():
    doc = make_loaded_doc([])
    structure = make_empty_structure()
    chunks = chunk_document(doc, structure, "doc_test", "v_001")
    assert chunks == []

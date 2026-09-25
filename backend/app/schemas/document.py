from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class DocumentType(str, Enum):
    book = "book"
    research_paper = "research_paper"
    report = "report"
    study_material = "study_material"
    notes = "notes"
    documentation = "documentation"
    article = "article"
    manual = "manual"
    other = "other"


class DocumentStatus(str, Enum):
    uploading = "uploading"
    queued = "queued"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class FileInfo(BaseModel):
    filename: str
    format: str
    size: int


class ProcessingInfo(BaseModel):
    pages: Optional[int] = None
    chunks: Optional[int] = None
    embedding_model: Optional[str] = None
    processed_at: Optional[datetime] = None


# ── Requests ──────────────────────────────────────────────────────────────────

class DocumentCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    author: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = Field(None, max_length=2000)
    document_type: DocumentType = DocumentType.other


class DocumentUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    author: Optional[str] = None
    description: Optional[str] = None
    document_type: Optional[DocumentType] = None


# ── Responses ─────────────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    id: str
    user_id: str
    title: str
    author: Optional[str] = None
    description: Optional[str] = None
    document_type: DocumentType
    file: FileInfo
    status: DocumentStatus
    processing: Optional[ProcessingInfo] = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_mongo(cls, doc: dict) -> "DocumentResponse":
        return cls(
            id=str(doc["_id"]),
            user_id=doc["user_id"],
            title=doc["title"],
            author=doc.get("author"),
            description=doc.get("description"),
            document_type=doc["document_type"],
            file=FileInfo(**doc["file"]),
            status=doc["status"],
            processing=ProcessingInfo(**doc["processing"]) if doc.get("processing") else None,
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total: int


class SectionResponse(BaseModel):
    id: str
    document_id: str
    title: str
    level: int
    parent_id: Optional[str] = None
    page: Optional[int] = None
    order: int

    @classmethod
    def from_mongo(cls, doc: dict) -> "SectionResponse":
        return cls(
            id=str(doc["_id"]),
            document_id=doc["document_id"],
            title=doc["title"],
            level=doc["level"],
            parent_id=doc.get("parent_id"),
            page=doc.get("page_number", doc.get("page")),
            order=doc.get("order", 0),
        )

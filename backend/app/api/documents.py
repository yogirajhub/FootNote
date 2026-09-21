"""
Documents API — upload, list, get, delete, status.
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, status
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.schemas.document import (
    DocumentResponse, DocumentListResponse, DocumentUpdateRequest,
    DocumentType, SectionResponse,
)
from app.schemas.processing import ProcessingJobResponse
from app.services import document_service
from app.api.deps import get_current_user
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    author: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    document_type: DocumentType = Form(DocumentType.other),
    user_id: str = Depends(get_current_user),
):
    """Upload a document and start processing."""
    # Validate extension
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lstrip(".").lower()
    if ext not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{ext}. Supported: {', '.join(settings.allowed_extensions)}",
        )

    # Validate size
    content = await file.read()
    if len(content) > settings.max_upload_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.max_upload_size // 1024 // 1024}MB",
        )

    # Save file
    upload_dir = Path(settings.upload_dir) / user_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuid.uuid4().hex}_{Path(filename).stem[:50]}.{ext}"
    file_path = str(upload_dir / safe_name)

    with open(file_path, "wb") as f:
        f.write(content)

    # Create document and trigger processing
    doc = await document_service.create_document(
        user_id=user_id,
        title=title,
        author=author,
        description=description,
        document_type=document_type,
        filename=filename,
        file_format=ext,
        file_size=len(content),
        file_path=file_path,
    )

    return DocumentResponse.from_mongo(doc)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    skip: int = 0,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
):
    docs, total = await document_service.list_documents(user_id, skip=skip, limit=limit)
    return DocumentListResponse(
        documents=[DocumentResponse.from_mongo(d) for d in docs],
        total=total,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, user_id: str = Depends(get_current_user)):
    doc = await document_service.get_document(document_id, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.from_mongo(doc)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: str,
    body: DocumentUpdateRequest,
    user_id: str = Depends(get_current_user),
):
    updates = body.model_dump(exclude_none=True)
    doc = await document_service.update_document(document_id, user_id, updates)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.from_mongo(doc)


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: str, user_id: str = Depends(get_current_user)):
    deleted = await document_service.delete_document(document_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")


@router.get("/{document_id}/status", response_model=ProcessingJobResponse)
async def get_document_status(document_id: str, user_id: str = Depends(get_current_user)):
    doc = await document_service.get_document(document_id, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    job = await document_service.get_processing_job(document_id)
    if not job:
        raise HTTPException(status_code=404, detail="Processing job not found")
    return ProcessingJobResponse.from_mongo(job)


@router.get("/{document_id}/sections")
async def get_document_sections(document_id: str, user_id: str = Depends(get_current_user)):
    doc = await document_service.get_document(document_id, user_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    from app.db.mongodb import document_sections_col
    cursor = document_sections_col().find(
        {"document_id": document_id}
    ).sort("order", 1)
    sections = await cursor.to_list(length=500)
    return {"sections": [SectionResponse.from_mongo(s) for s in sections]}

"""
Document service — business logic for document management.
No MongoDB queries inside route handlers.
"""
import os
import uuid
import shutil
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Any
from pathlib import Path

from app.config.settings import settings
from app.db.mongodb import documents_col, processing_jobs_col
from app.schemas.document import DocumentType, DocumentStatus
import structlog

logger = structlog.get_logger()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_document(
    user_id: str,
    title: str,
    author: Optional[str],
    description: Optional[str],
    document_type: DocumentType,
    filename: str,
    file_format: str,
    file_size: int,
    file_path: str,
    background_tasks: Optional[Any] = None,
) -> dict:
    """Create document record and trigger background processing with low latency."""
    doc_id = f"doc_{uuid.uuid4().hex[:16]}"
    now = _now()

    doc = {
        "_id": doc_id,
        "user_id": user_id,
        "title": title,
        "author": author,
        "description": description,
        "document_type": document_type,
        "file": {
            "filename": filename,
            "format": file_format,
            "size": file_size,
            "path": file_path,
            "storage_id": None,
        },
        "status": DocumentStatus.queued,
        "processing": None,
        "created_at": now,
        "updated_at": now,
    }

    await documents_col().insert_one(doc)
    logger.info("Document created", doc_id=doc_id, title=title)

    # Create processing job
    job_id = await _create_processing_job(doc_id)

    # Trigger background processing
    if background_tasks:
        background_tasks.add_task(_process_document_background, doc_id, job_id, file_path)
    else:
        asyncio.create_task(_process_document_background(doc_id, job_id, file_path))

    return doc


async def get_document(document_id: str, user_id: str) -> Optional[dict]:
    return await documents_col().find_one({"_id": document_id, "user_id": user_id})


async def list_documents(user_id: str, skip: int = 0, limit: int = 50) -> tuple[List[dict], int]:
    col = documents_col()
    total = await col.count_documents({"user_id": user_id})
    cursor = col.find({"user_id": user_id}).sort("created_at", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    return docs, total


async def delete_document(document_id: str, user_id: str) -> bool:
    """Delete document and all associated data."""
    from app.ingestion.indexer import delete_document_chunks, delete_document_sections
    from app.ingestion.pages import delete_document_pages
    from app.services.notes_service import delete_document_notes

    doc = await documents_col().find_one({"_id": document_id, "user_id": user_id})
    if not doc:
        return False

    # Delete file on disk and the original copy in the database
    file_info = doc.get("file") or {}
    file_path = file_info.get("path")
    if file_path and os.path.exists(file_path):
        os.remove(file_path)

    from app.services.original_file_service import delete_original_file
    await delete_original_file(document_id, file_info.get("storage_id"))

    # Delete chunks, sections, pages, and notes
    await delete_document_chunks(document_id)
    await delete_document_sections(document_id)
    await delete_document_pages(document_id)
    await delete_document_notes(document_id)

    # Invalidate vector cache
    from app.rag.retriever import invalidate_document_cache
    invalidate_document_cache(document_id)

    # Delete document record
    await documents_col().delete_one({"_id": document_id})
    logger.info("Document deleted", document_id=document_id)
    return True


async def update_document(document_id: str, user_id: str, updates: dict) -> Optional[dict]:
    updates["updated_at"] = _now()
    result = await documents_col().find_one_and_update(
        {"_id": document_id, "user_id": user_id},
        {"$set": updates},
        return_document=True,
    )
    return result


async def _create_processing_job(document_id: str) -> str:
    job_id = f"job_{uuid.uuid4().hex[:16]}"
    now = _now()
    await processing_jobs_col().insert_one({
        "_id": job_id,
        "document_id": document_id,
        "status": "queued",
        "current_stage": None,
        "progress": 0,
        "pages_processed": 0,
        "chunks_created": 0,
        "embeddings_created": 0,
        "error": None,
        "started_at": None,
        "completed_at": None,
        "created_at": now,
    })
    return job_id


async def get_processing_job(document_id: str) -> Optional[dict]:
    return await processing_jobs_col().find_one(
        {"document_id": document_id},
        sort=[("created_at", -1)],
    )


async def _update_job(job_id: str, updates: dict) -> None:
    await processing_jobs_col().update_one({"_id": job_id}, {"$set": updates})


async def _process_document_background(
    document_id: str,
    job_id: str,
    file_path: str,
) -> None:
    """Full document processing pipeline run as background task."""
    from app.ingestion.pipeline import run_ingestion

    version_id = f"v_{uuid.uuid4().hex[:8]}"

    try:
        # Asynchronously ensure original file is stored in GridFS in the background
        from app.services.original_file_service import ensure_original_file
        try:
            doc = await documents_col().find_one({"_id": document_id})
            if doc and not (doc.get("file") or {}).get("storage_id"):
                await ensure_original_file(doc)
        except Exception as file_err:
            logger.warning("Could not persist original file into GridFS during background task", error=str(file_err), document_id=document_id)

        # ── Real-time progress reporter ─────────────────────────────────────
        async def report_progress(stage: str, progress: int, pages: int = 0, chunks: int = 0, embeddings: int = 0):
            update_data: dict[str, Any] = {
                "current_stage": stage,
                "progress": progress,
            }
            if pages > 0:
                update_data["pages_processed"] = pages
            if chunks > 0:
                update_data["chunks_created"] = chunks
            if embeddings > 0:
                update_data["embeddings_created"] = embeddings
            await _update_job(job_id, update_data)

        # ── Update status: processing ──────────────────────────────────────
        await _update_job(job_id, {
            "status": "processing",
            "current_stage": "extraction",
            "started_at": _now(),
            "progress": 5,
        })
        await documents_col().update_one(
            {"_id": document_id},
            {"$set": {"status": DocumentStatus.processing, "updated_at": _now()}},
        )

        stored = await run_ingestion(document_id, file_path, version_id, on_progress=report_progress)

        # ── Done ───────────────────────────────────────────────────────────
        now = _now()
        await _update_job(job_id, {
            "status": "completed",
            "current_stage": "completed",
            "progress": 100,
            "embeddings_created": stored,
            "completed_at": now,
        })
        
        # We need total pages for document status
        from app.db.mongodb import document_pages_col
        total_pages = await document_pages_col().count_documents({"document_id": document_id})
        
        await documents_col().update_one(
            {"_id": document_id},
            {"$set": {
                "status": DocumentStatus.ready,
                "updated_at": now,
                "processing": {
                    "pages": total_pages,
                    "chunks": stored,
                    "embedding_model": settings.embedding_model,
                    "processed_at": now,
                },
            }},
        )
        logger.info("Document processing complete", document_id=document_id, chunks=stored)

    except Exception as e:
        logger.error("Document processing failed", document_id=document_id, error=str(e))
        now = _now()
        await _update_job(job_id, {
            "status": "failed",
            "error": str(e),
            "completed_at": now,
        })
        await documents_col().update_one(
            {"_id": document_id},
            {"$set": {"status": DocumentStatus.failed, "updated_at": now}},
        )

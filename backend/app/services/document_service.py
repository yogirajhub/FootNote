"""
Document service — business logic for document management.
No MongoDB queries inside route handlers.
"""
import os
import uuid
import shutil
import asyncio
from datetime import datetime, timezone
from typing import Optional, List
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
) -> dict:
    """Create document record and trigger background processing."""
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

    doc = await documents_col().find_one({"_id": document_id, "user_id": user_id})
    if not doc:
        return False

    # Delete file
    file_path = doc.get("file", {}).get("path")
    if file_path and os.path.exists(file_path):
        os.remove(file_path)

    # Delete chunks and sections
    await delete_document_chunks(document_id)
    await delete_document_sections(document_id)

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
    from app.ingestion.parser import parse_document
    from app.ingestion.structure_detector import detect_structure
    from app.ingestion.chunker import chunk_document
    from app.ingestion.indexer import store_sections, store_chunks_with_embeddings
    from app.rag.embeddings import embedding_service

    version_id = f"v_{uuid.uuid4().hex[:8]}"

    try:
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

        # ── Stage 1: Parse document ────────────────────────────────────────
        logger.info("Stage: extraction", document_id=document_id)
        loaded_doc = parse_document(file_path)
        await _update_job(job_id, {
            "current_stage": "structure_detection",
            "pages_processed": loaded_doc.total_pages,
            "progress": 20,
        })

        # ── Stage 2: Detect structure ──────────────────────────────────────
        logger.info("Stage: structure_detection", document_id=document_id)
        structure = detect_structure(loaded_doc)
        await store_sections(structure.sections, document_id, version_id)
        await _update_job(job_id, {
            "current_stage": "chunking",
            "progress": 35,
        })

        # ── Stage 3: Chunk ─────────────────────────────────────────────────
        logger.info("Stage: chunking", document_id=document_id)
        chunks = chunk_document(loaded_doc, structure, document_id, version_id)
        await _update_job(job_id, {
            "current_stage": "embedding",
            "chunks_created": len(chunks),
            "progress": 50,
        })

        # ── Stage 4: Generate embeddings ───────────────────────────────────
        logger.info("Stage: embedding", document_id=document_id, chunks=len(chunks))
        texts = [c.content for c in chunks]
        embeddings = embedding_service.embed_texts(texts, batch_size=32)
        await _update_job(job_id, {
            "current_stage": "indexing",
            "embeddings_created": len(embeddings),
            "progress": 80,
        })

        # ── Stage 5: Store chunks + embeddings ─────────────────────────────
        logger.info("Stage: indexing", document_id=document_id)
        stored = await store_chunks_with_embeddings(
            chunks, embeddings, document_id, version_id
        )

        # ── Done ───────────────────────────────────────────────────────────
        now = _now()
        await _update_job(job_id, {
            "status": "completed",
            "current_stage": "completed",
            "progress": 100,
            "embeddings_created": stored,
            "completed_at": now,
        })
        await documents_col().update_one(
            {"_id": document_id},
            {"$set": {
                "status": DocumentStatus.ready,
                "updated_at": now,
                "processing": {
                    "pages": loaded_doc.total_pages,
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

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from app.db.mongodb import document_pages_col
from app.ingestion.loaders.base import DocumentPage
import structlog

logger = structlog.get_logger()

async def store_pages(pages: List[DocumentPage], document_id: str, version_id: str) -> int:
    if not pages:
        return 0

    col = document_pages_col()
    docs = []
    
    for i, page in enumerate(pages):
        page_num = page.page_number if page.page_number is not None else i + 1
        docs.append({
            "document_id": document_id,
            "version_id": version_id,
            "page_number": page_num,
            "content": page.content,
            "metadata": page.metadata,
            "created_at": datetime.now(timezone.utc),
        })

    try:
        result = await col.insert_many(docs, ordered=False)
        logger.info("Pages stored", count=len(result.inserted_ids), document_id=document_id)
        return len(result.inserted_ids)
    except Exception as e:
        logger.error("Failed to store pages", error=str(e), document_id=document_id)
        raise

async def delete_document_pages(document_id: str) -> int:
    col = document_pages_col()
    result = await col.delete_many({"document_id": document_id})
    logger.info("Pages deleted", document_id=document_id, count=result.deleted_count)
    return result.deleted_count

async def get_page(document_id: str, page_number: int) -> Optional[Dict[str, Any]]:
    col = document_pages_col()
    return await col.find_one({"document_id": document_id, "page_number": page_number})

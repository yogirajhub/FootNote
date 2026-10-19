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


def page_heading_and_preview(content: str) -> tuple[str, str]:
    """First short line as a heading, then the opening text for hover previews."""
    lines = [ln.strip() for ln in (content or "").replace("\r\n", "\n").split("\n") if ln.strip()]
    heading = ""
    for line in lines[:8]:
        if 2 <= len(line) <= 100:
            heading = line
            break

    body = lines[1:] if heading and lines and lines[0] == heading else lines
    preview = " ".join(body).strip()
    if len(preview) > 180:
        preview = preview[:177].rstrip() + "…"
    return heading, preview


async def list_pages(document_id: str) -> List[Dict[str, Any]]:
    col = document_pages_col()
    cursor = col.find(
        {"document_id": document_id},
        {"_id": 0, "page_number": 1, "content": 1},
    ).sort("page_number", 1)
    docs = await cursor.to_list(length=5000)

    items: List[Dict[str, Any]] = []
    for doc in docs:
        content = doc.get("content") or ""
        heading, preview = page_heading_and_preview(content)
        items.append({
            "page": doc.get("page_number"),
            "content": content,
            "heading": heading,
            "preview": preview,
        })
    return items

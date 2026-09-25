"""
Notes service — CRUD for user notes, scoped by user_id.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from app.db.mongodb import notes_col
import structlog

logger = structlog.get_logger()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_note(
    user_id: str,
    document_id: str,
    content: str,
    page: Optional[int] = None,
    source: Optional[str] = None,  # "selection" | "answer" | "manual"
) -> dict:
    note_id = f"note_{uuid.uuid4().hex[:16]}"
    now = _now()
    doc = {
        "_id": note_id,
        "user_id": user_id,
        "document_id": document_id,
        "content": content,
        "page": page,
        "source": source or "manual",
        "created_at": now,
        "updated_at": now,
    }
    await notes_col().insert_one(doc)
    logger.info("Note created", note_id=note_id, document_id=document_id)
    return doc


async def list_notes(
    user_id: str,
    document_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[List[dict], int]:
    query: dict = {"user_id": user_id}
    if document_id:
        query["document_id"] = document_id

    col = notes_col()
    total = await col.count_documents(query)
    cursor = col.find(query).sort("created_at", -1).skip(skip).limit(limit)
    notes = await cursor.to_list(length=limit)
    return notes, total


async def update_note(note_id: str, user_id: str, content: str) -> Optional[dict]:
    result = await notes_col().find_one_and_update(
        {"_id": note_id, "user_id": user_id},
        {"$set": {"content": content, "updated_at": _now()}},
        return_document=True,
    )
    return result


async def delete_note(note_id: str, user_id: str) -> bool:
    result = await notes_col().delete_one({"_id": note_id, "user_id": user_id})
    return result.deleted_count > 0


async def delete_document_notes(document_id: str) -> int:
    result = await notes_col().delete_many({"document_id": document_id})
    logger.info("Notes deleted", document_id=document_id, count=result.deleted_count)
    return result.deleted_count

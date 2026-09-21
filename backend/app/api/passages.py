"""
Passages API — fetch passage details, find related passages, bookmark.
"""
from fastapi import APIRouter, HTTPException, Depends
from app.api.deps import get_current_user
from app.rag.retriever import get_chunk_by_id, retrieve
from app.db.mongodb import document_chunks_col, bookmarks_col, documents_col
from app.schemas.chat import PassageResponse, SourceLocation
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/passages", tags=["passages"])


@router.get("/{chunk_id}")
async def get_passage(chunk_id: str, user_id: str = Depends(get_current_user)):
    chunk = await get_chunk_by_id(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Passage not found")

    # Verify document ownership
    doc = await documents_col().find_one({"_id": chunk.document_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=403, detail="Access denied")

    meta = chunk.metadata
    return PassageResponse(
        chunk_id=chunk.chunk_id,
        content=chunk.content,
        source=SourceLocation(
            document_id=chunk.document_id,
            document_title=doc["title"],
            chapter=meta.get("chapter"),
            section=meta.get("section"),
            page=meta.get("page"),
            chunk_id=chunk.chunk_id,
        ),
        relevance_score=chunk.score,
    )


@router.get("/{chunk_id}/related")
async def get_related_passages(
    chunk_id: str,
    user_id: str = Depends(get_current_user),
):
    """Find passages related to the given chunk using its content as query."""
    chunk = await get_chunk_by_id(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Passage not found")

    doc = await documents_col().find_one({"_id": chunk.document_id, "user_id": user_id})
    if not doc:
        raise HTTPException(status_code=403, detail="Access denied")

    # Use chunk content as query to find related passages
    query = chunk.content[:200]
    related = await retrieve(query=query, document_id=chunk.document_id, top_k=5)

    # Exclude the chunk itself
    related = [r for r in related if r.chunk_id != chunk_id][:4]

    results = []
    for r in related:
        meta = r.metadata
        results.append(PassageResponse(
            chunk_id=r.chunk_id,
            content=r.content,
            source=SourceLocation(
                document_id=r.document_id,
                document_title=doc["title"],
                chapter=meta.get("chapter"),
                section=meta.get("section"),
                page=meta.get("page"),
                chunk_id=r.chunk_id,
            ),
            relevance_score=r.score,
        ))

    return {"related_passages": results}


@router.post("/{chunk_id}/bookmark", status_code=201)
async def bookmark_passage(chunk_id: str, user_id: str = Depends(get_current_user)):
    chunk = await get_chunk_by_id(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Passage not found")

    # Check if already bookmarked
    existing = await bookmarks_col().find_one({
        "user_id": user_id,
        "chunk_id": chunk_id,
    })
    if existing:
        return {"message": "Already bookmarked", "bookmark_id": str(existing["_id"])}

    bookmark_id = f"bm_{uuid.uuid4().hex[:12]}"
    await bookmarks_col().insert_one({
        "_id": bookmark_id,
        "user_id": user_id,
        "chunk_id": chunk_id,
        "document_id": chunk.document_id,
        "content_excerpt": chunk.content[:200],
        "created_at": datetime.now(timezone.utc),
    })
    return {"message": "Bookmarked successfully", "bookmark_id": bookmark_id}


@router.get("/bookmarks/me")
async def get_my_bookmarks(user_id: str = Depends(get_current_user)):
    cursor = bookmarks_col().find({"user_id": user_id}).sort("created_at", -1).limit(50)
    bookmarks = await cursor.to_list(length=50)
    return {"bookmarks": bookmarks}

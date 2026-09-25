"""
Notes API — CRUD for reading notes.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.services import notes_service
from app.api.deps import get_current_user
import structlog

logger = structlog.get_logger()
router = APIRouter(prefix="/notes", tags=["notes"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class NoteCreateRequest(BaseModel):
    document_id: str
    content: str = Field(..., min_length=1, max_length=5000)
    page: Optional[int] = None
    source: Optional[str] = "manual"  # "selection" | "answer" | "manual"


class NoteUpdateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class NoteResponse(BaseModel):
    id: str
    document_id: str
    content: str
    page: Optional[int] = None
    source: str
    created_at: str
    updated_at: str

    @classmethod
    def from_mongo(cls, doc: dict) -> "NoteResponse":
        return cls(
            id=str(doc["_id"]),
            document_id=doc["document_id"],
            content=doc["content"],
            page=doc.get("page"),
            source=doc.get("source", "manual"),
            created_at=doc["created_at"].isoformat(),
            updated_at=doc["updated_at"].isoformat(),
        )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", response_model=NoteResponse, status_code=201)
async def create_note(
    body: NoteCreateRequest,
    user_id: str = Depends(get_current_user),
):
    note = await notes_service.create_note(
        user_id=user_id,
        document_id=body.document_id,
        content=body.content,
        page=body.page,
        source=body.source,
    )
    return NoteResponse.from_mongo(note)


@router.get("")
async def list_notes(
    document_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    user_id: str = Depends(get_current_user),
):
    notes, total = await notes_service.list_notes(
        user_id=user_id,
        document_id=document_id,
        skip=skip,
        limit=limit,
    )
    return {
        "notes": [NoteResponse.from_mongo(n) for n in notes],
        "total": total,
    }


@router.patch("/{note_id}", response_model=NoteResponse)
async def update_note(
    note_id: str,
    body: NoteUpdateRequest,
    user_id: str = Depends(get_current_user),
):
    note = await notes_service.update_note(note_id, user_id, body.content)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return NoteResponse.from_mongo(note)


@router.delete("/{note_id}", status_code=204)
async def delete_note(
    note_id: str,
    user_id: str = Depends(get_current_user),
):
    deleted = await notes_service.delete_note(note_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")

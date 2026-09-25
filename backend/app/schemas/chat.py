from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Any
from datetime import datetime


class SourceLocation(BaseModel):
    document_id: str
    document_title: str
    chapter: Optional[str] = None
    section: Optional[str] = None
    page: Optional[int] = None
    chunk_id: Optional[str] = None


class PassageResponse(BaseModel):
    chunk_id: str
    content: str
    source: SourceLocation
    relevance_score: Optional[float] = None


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    document_id: str
    message: str = Field(..., min_length=1, max_length=4000)
    mode: Literal["document", "library"] = "document"
    document_ids: Optional[List[str]] = None  # for library/cross-doc mode


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    evidence: Optional[List[dict]] = None
    intent: Optional[str] = None
    created_at: datetime

    @classmethod
    def from_mongo(cls, doc: dict) -> "MessageResponse":
        return cls(
            id=str(doc["_id"]),
            conversation_id=doc["conversation_id"],
            role=doc["role"],
            content=doc["content"],
            evidence=doc.get("evidence"),
            intent=doc.get("intent"),
            created_at=doc["created_at"],
        )


class ConversationResponse(BaseModel):
    id: str
    user_id: str
    document_id: str
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    @classmethod
    def from_mongo(cls, doc: dict) -> "ConversationResponse":
        return cls(
            id=str(doc["_id"]),
            user_id=doc["user_id"],
            document_id=doc["document_id"],
            title=doc.get("title"),
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
            message_count=doc.get("message_count", 0),
        )


class ConversationListResponse(BaseModel):
    conversations: List[ConversationResponse]
    total: int


class ConversationDetailResponse(BaseModel):
    conversation: ConversationResponse
    messages: List[MessageResponse]


class ChatResponse(BaseModel):
    conversation_id: str
    message: MessageResponse
    intent: str
    processing_time_ms: Optional[int] = None

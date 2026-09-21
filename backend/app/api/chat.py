"""
Chat API — send messages, list/get conversations.
"""
from fastapi import APIRouter, HTTPException, Depends
from app.schemas.chat import (
    ChatRequest, ChatResponse, ConversationListResponse,
    ConversationDetailResponse, ConversationResponse, MessageResponse,
)
from app.services import chat_service
from app.api.deps import get_current_user
import structlog

logger = structlog.get_logger()
router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    user_id: str = Depends(get_current_user),
):
    """Send a message and get a RAG-powered response."""
    try:
        result = await chat_service.process_chat(request, user_id)
        return ChatResponse(
            conversation_id=result["conversation_id"],
            message=MessageResponse.from_mongo(result["message"]),
            passages=result["passages"],
            intent=result["intent"],
            processing_time_ms=result["processing_time_ms"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Chat processing error", error=str(e))
        raise HTTPException(status_code=500, detail="An error occurred processing your message")


@router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    document_id: str = None,
    user_id: str = Depends(get_current_user),
):
    convs, total = await chat_service.list_conversations(user_id, document_id=document_id)
    return ConversationListResponse(
        conversations=[ConversationResponse.from_mongo(c) for c in convs],
        total=total,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user),
):
    detail = await chat_service.get_conversation_detail(conversation_id, user_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationDetailResponse(
        conversation=ConversationResponse.from_mongo(detail["conversation"]),
        messages=[MessageResponse.from_mongo(m) for m in detail["messages"]],
    )

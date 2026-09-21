"""
Chat service — manages conversations and executes the RAG pipeline.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict

from app.db.mongodb import conversations_col, messages_col, documents_col
from app.rag.pipeline import run_rag_pipeline
from app.schemas.chat import ChatRequest
import structlog

logger = structlog.get_logger()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def get_or_create_conversation(
    user_id: str,
    document_id: str,
    conversation_id: Optional[str],
    first_message: str,
) -> dict:
    """Return existing conversation or create a new one."""
    if conversation_id:
        conv = await conversations_col().find_one({
            "_id": conversation_id,
            "user_id": user_id,
            "document_id": document_id,
        })
        if conv:
            return conv

    # Create new conversation
    conv_id = f"conv_{uuid.uuid4().hex[:16]}"
    now = _now()
    title = first_message[:60] + ("..." if len(first_message) > 60 else "")
    conv = {
        "_id": conv_id,
        "user_id": user_id,
        "document_id": document_id,
        "title": title,
        "message_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    await conversations_col().insert_one(conv)
    return conv


async def get_conversation_history(conversation_id: str, limit: int = 10) -> List[Dict]:
    """Get recent messages from a conversation as a list of dicts."""
    cursor = messages_col().find(
        {"conversation_id": conversation_id}
    ).sort("created_at", 1).limit(limit)
    messages = await cursor.to_list(length=limit)
    return [{"role": m["role"], "content": m["content"]} for m in messages]


async def save_message(
    conversation_id: str,
    role: str,
    content: str,
    passages: Optional[list] = None,
    intent: Optional[str] = None,
) -> dict:
    msg_id = f"msg_{uuid.uuid4().hex[:16]}"
    now = _now()
    msg = {
        "_id": msg_id,
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "passages": passages or [],
        "intent": intent,
        "created_at": now,
    }
    await messages_col().insert_one(msg)
    await conversations_col().update_one(
        {"_id": conversation_id},
        {"$set": {"updated_at": now}, "$inc": {"message_count": 1}},
    )
    return msg


async def process_chat(request: ChatRequest, user_id: str) -> dict:
    """
    Main chat processing function.
    1. Load document
    2. Get/create conversation
    3. Load history
    4. Run RAG pipeline
    5. Save messages
    6. Return response
    """
    # Load document
    doc = await documents_col().find_one({"_id": request.document_id, "user_id": user_id})
    if not doc:
        raise ValueError(f"Document not found: {request.document_id}")
    if doc["status"] != "ready":
        raise ValueError(f"Document is not ready (status: {doc['status']}). Please wait for processing to complete.")

    # Get or create conversation
    conversation = await get_or_create_conversation(
        user_id=user_id,
        document_id=request.document_id,
        conversation_id=request.conversation_id,
        first_message=request.message,
    )
    conversation_id = conversation["_id"]

    # Save user message
    await save_message(conversation_id, "user", request.message)

    # Load conversation history for context
    history = await get_conversation_history(conversation_id, limit=8)

    # Run RAG pipeline
    result = await run_rag_pipeline(
        query=request.message,
        document_id=request.document_id,
        document_title=doc["title"],
        conversation_history=history[:-1],  # exclude the message we just saved
        document_ids=request.document_ids if request.mode == "library" else None,
    )

    # Serialize passages for storage
    passages_data = []
    for chunk in result.passages:
        meta = chunk.metadata
        passages_data.append({
            "chunk_id": chunk.chunk_id,
            "content": chunk.content[:500],  # store excerpt
            "source": {
                "document_id": chunk.document_id,
                "document_title": doc["title"],
                "chapter": meta.get("chapter"),
                "section": meta.get("section"),
                "page": meta.get("page"),
                "chunk_id": chunk.chunk_id,
            },
            "relevance_score": chunk.score,
        })

    # Save assistant message
    assistant_msg = await save_message(
        conversation_id=conversation_id,
        role="assistant",
        content=result.answer,
        passages=passages_data,
        intent=result.intent.value,
    )

    return {
        "conversation_id": conversation_id,
        "message": assistant_msg,
        "passages": passages_data,
        "intent": result.intent.value,
        "processing_time_ms": result.latency_ms,
    }


async def list_conversations(user_id: str, document_id: Optional[str] = None) -> tuple[List[dict], int]:
    query: Dict = {"user_id": user_id}
    if document_id:
        query["document_id"] = document_id
    col = conversations_col()
    total = await col.count_documents(query)
    cursor = col.find(query).sort("updated_at", -1).limit(50)
    convs = await cursor.to_list(length=50)
    return convs, total


async def get_conversation_detail(conversation_id: str, user_id: str) -> Optional[dict]:
    conv = await conversations_col().find_one({"_id": conversation_id, "user_id": user_id})
    if not conv:
        return None
    cursor = messages_col().find({"conversation_id": conversation_id}).sort("created_at", 1)
    messages = await cursor.to_list(length=200)
    return {"conversation": conv, "messages": messages}

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_to_mongo() -> None:
    global _client, _db
    
    # Mask credentials for logging
    uri_to_log = settings.mongodb_uri
    if "@" in uri_to_log:
        prefix, suffix = uri_to_log.split("@", 1)
        if "://" in prefix:
            scheme, auth = prefix.split("://", 1)
            if ":" in auth:
                username, _ = auth.split(":", 1)
                uri_to_log = f"{scheme}://{username}:***@{suffix}"
            else:
                uri_to_log = f"{scheme}://***@{suffix}"
    
    logger.info("Connecting to MongoDB", uri=uri_to_log)
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    _db = _client[settings.mongodb_database]
    await _create_indexes()
    logger.info("MongoDB connected", database=settings.mongodb_database)


async def close_mongo_connection() -> None:
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB connection closed")


def get_database() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not initialised — call connect_to_mongo first")
    return _db


def get_collection(name: str):
    return get_database()[name]


# ── Collection accessors ───────────────────────────────────────────────────────

def users_col():
    return get_collection("users")

def documents_col():
    return get_collection("documents")

def document_versions_col():
    return get_collection("document_versions")

def document_sections_col():
    return get_collection("document_sections")

def document_chunks_col():
    return get_collection("document_chunks")

def conversations_col():
    return get_collection("conversations")

def messages_col():
    return get_collection("messages")

def bookmarks_col():
    return get_collection("bookmarks")

def notes_col():
    return get_collection("notes")

def document_pages_col():
    return get_collection("document_pages")

def feedback_col():
    return get_collection("feedback")

def processing_jobs_col():
    return get_collection("processing_jobs")


# ── Index creation ─────────────────────────────────────────────────────────────

async def _create_indexes() -> None:
    db = get_database()

    # documents
    await db.documents.create_index([("user_id", ASCENDING)])
    await db.documents.create_index([("status", ASCENDING)])
    await db.documents.create_index([("created_at", DESCENDING)])

    # document_chunks
    await db.document_chunks.create_index([("document_id", ASCENDING)])
    await db.document_chunks.create_index([("document_version_id", ASCENDING)])
    await db.document_chunks.create_index([("metadata.chapter", ASCENDING)])
    await db.document_chunks.create_index([("metadata.section", ASCENDING)])

    # conversations
    await db.conversations.create_index([("user_id", ASCENDING)])
    await db.conversations.create_index([("document_id", ASCENDING)])
    await db.conversations.create_index([("updated_at", DESCENDING)])

    # messages
    await db.messages.create_index([("conversation_id", ASCENDING)])
    await db.messages.create_index([("created_at", ASCENDING)])

    # processing_jobs
    await db.processing_jobs.create_index([("document_id", ASCENDING)])
    await db.processing_jobs.create_index([("status", ASCENDING)])

    # bookmarks
    await db.bookmarks.create_index([("user_id", ASCENDING)])
    await db.bookmarks.create_index([("document_id", ASCENDING)])

    # notes
    await db.notes.create_index([("user_id", ASCENDING), ("document_id", ASCENDING)])

    # document_pages
    await db.document_pages.create_index([("document_id", ASCENDING), ("page_number", ASCENDING)], unique=True)

    logger.info("MongoDB indexes created")

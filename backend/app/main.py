"""
FootNote — FastAPI application entry point.
"""
import structlog
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config.settings import settings
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.api import documents, chat, passages, health, notes

logger = structlog.get_logger()


import asyncio
from app.rag.embeddings import embedding_service
from app.rag.retriever import set_vector_search_available
from app.db.mongodb import document_chunks_col

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("Starting FootNote API", version=settings.app_version)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    await connect_to_mongo()
    
    if settings.embedding_warmup:
        logger.info("Warming up embedding model...")
        await embedding_service.async_warmup()
        
    # Probe vector search availability
    try:
        col = document_chunks_col()
        cursor = col.aggregate([
            {
                "$vectorSearch": {
                    "index": settings.vector_index_name,
                    "path": "embedding",
                    "queryVector": [0.0] * settings.embedding_dimensions,
                    "numCandidates": 1,
                    "limit": 1,
                }
            }
        ])
        # Try to execute the query
        async for _ in cursor:
            pass
        set_vector_search_available(True)
        logger.info("MongoDB $vectorSearch is available")
    except Exception as e:
        logger.warning("MongoDB $vectorSearch NOT available, will use numpy fallback", error=str(e))
        set_vector_search_available(False)
        
    yield
    # Shutdown
    await close_mongo_connection()
    logger.info("FootNote API stopped")


app = FastAPI(
    title="FootNote API",
    description="Document-grounded conversational RAG platform",
    version=settings.app_version,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(passages.router, prefix="/api")
app.include_router(notes.router, prefix="/api")


@app.get("/")
async def root():
    return {"name": settings.app_name, "version": settings.app_version, "tagline": "Turn every document into a conversation."}

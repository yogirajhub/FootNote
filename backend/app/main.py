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
from app.api import documents, chat, passages, health

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("Starting FootNote API", version=settings.app_version)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    await connect_to_mongo()
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


@app.get("/")
async def root():
    return {"name": settings.app_name, "version": settings.app_version, "tagline": "Turn every document into a conversation."}

"""Health check API."""
from fastapi import APIRouter
from app.db.mongodb import get_database
from app.config.settings import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Basic health check."""
    db_ok = False
    try:
        db = get_database()
        await db.command("ping")
        db_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "version": settings.app_version,
        "embedding_model": settings.embedding_model,
        "llm_model": settings.llm_model,
    }

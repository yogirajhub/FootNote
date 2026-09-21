"""
Dependencies — FastAPI dependency injection.
Demo user for MVP; structure ready for real JWT auth.
"""
from fastapi import Header, HTTPException
from app.config.settings import settings


async def get_current_user(x_user_id: str = Header(default=None)) -> str:
    """
    MVP: Returns demo user ID from header or settings.
    Production: Replace with JWT token validation.
    """
    if x_user_id:
        return x_user_id
    return settings.demo_user_id

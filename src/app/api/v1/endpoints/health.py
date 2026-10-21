"""Health/readiness endpoints."""

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.core.config import Settings
from app.infrastructure.database.session import Database

router = APIRouter()


@router.get(
    "/health",
    summary="Readiness check",
    description="Verifies the process is up AND the database is reachable.",
)
async def health_check(request: Request) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    database: Database = request.app.state.database
    async with database.session() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ok", "version": settings.app_version}

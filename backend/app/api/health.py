from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config.settings import get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str = Field(description="Current service health status.")
    service: str = Field(description="Service display name.")
    timestamp: datetime = Field(description="UTC timestamp when the health check was produced.")


@router.get("/health", response_model=HealthResponse, summary="Service health check")
async def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        timestamp=datetime.now(UTC),
    )

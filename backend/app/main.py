from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.api.context_routes import router as context_router
from app.api.health import router as health_router
from app.api.medrec_routes import router as medrec_router
from app.api.orchestrator_routes import router as orchestrator_router
from app.api.transition_routes import router as transition_router
from app.config.settings import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # TODO: Initialize database pools, external clients, and background workers.
    yield
    # TODO: Gracefully close infrastructure resources during shutdown.


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "CareBridge AI backend for transition-of-care workflows built around "
            "an R4-compliant interoperability baseline with selective R5 feature support."
        ),
        lifespan=lifespan,
    )

    app.include_router(health_router)
    app.include_router(orchestrator_router)
    app.include_router(context_router)
    app.include_router(medrec_router)
    app.include_router(transition_router)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled application exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error."},
        )

    return app


app = create_app()

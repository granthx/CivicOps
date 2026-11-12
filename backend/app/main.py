"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from .config import settings
from .database import SessionLocal, init_db
from .errors import AppError
from .models import User
from .routers import analytics, auth, chat, incidents, media, meta, reports, work_orders
from .seed import seed_demo_data
from .services.sla import sweep_sla_escalations

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


async def _sla_sweep_loop(interval_seconds: int) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            with SessionLocal() as db:
                result = sweep_sla_escalations(db)
                if result.escalated_count > 0:
                    logger.info(
                        "Background SLA sweep escalated %d work orders.",
                        result.escalated_count,
                    )
        except Exception:
            logger.exception("Background SLA sweep failed.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    if settings.auto_create_tables:
        init_db()
    if settings.seed_on_startup:
        with SessionLocal() as db:
            existing = db.scalar(select(User.id).limit(1))
        if existing is None:
            with SessionLocal() as db:
                seed_demo_data(db)
                logger.info("Synthetic demo data seeded.")
    sweep_task: asyncio.Task[None] | None = None
    if settings.sla_sweep_interval_seconds > 0:
        sweep_task = asyncio.create_task(
            _sla_sweep_loop(settings.sla_sweep_interval_seconds)
        )
    try:
        yield
    finally:
        if sweep_task is not None:
            sweep_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sweep_task


app = FastAPI(
    title="CivicOps AI API",
    version="0.1.0",
    description=(
        "Waste-management intake, human-reviewed incident operations, work orders, "
        "evidence and audit APIs. Demo data is synthetic."
    ),
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(AppError)
def app_error_handler(_request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


@app.exception_handler(RequestValidationError)
def validation_error_handler(_request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Some submitted fields are invalid.",
            "code": "validation_error",
            "errors": exc.errors(),
        },
    )


@app.get("/api/health", tags=["system"])
def health() -> dict[str, str]:
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "data_mode": "synthetic demo" if settings.seed_on_startup else "configured",
    }


app.include_router(auth.router, prefix="/api")
app.include_router(meta.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(incidents.duplicate_router, prefix="/api")
app.include_router(work_orders.router, prefix="/api")
app.include_router(media.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(chat.router, prefix="/api")

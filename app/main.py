from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import DatabaseManager
from app.core.exceptions import AttendanceException
from app.routers import analytics, attendance

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger("hrone.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and shutdown lifecycle for MongoDB connections."""
    logger.info(f"Initializing {settings.APP_NAME} v{settings.APP_VERSION}")
    await DatabaseManager.connect_to_database()
    yield
    logger.info("Shutting down application and terminating database connections.")
    await DatabaseManager.close_database_connection()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise-grade Attendance & Analytics REST API for HROne with Motor & MongoDB.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Enable CORS for standard enterprise web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(AttendanceException)
async def attendance_exception_handler(
    request: Request, exc: AttendanceException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "error_code": exc.error_code,
            "message": exc.detail,
            "extra": exc.extra,
            "path": str(request.url.path),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    formatted_errors = []
    for err in exc.errors():
        field_path = " -> ".join(str(loc) for loc in err.get("loc", []))
        formatted_errors.append(
            {
                "field": field_path,
                "type": err.get("type"),
                "message": err.get("msg"),
            }
        )
    return JSONResponse(
        status_code=422,
        content={
            "error": True,
            "error_code": "VALIDATION_ERROR",
            "message": "Input validation failed. Please check payload parameters.",
            "details": formatted_errors,
            "path": str(request.url.path),
        },
    )


# Attach modular routers
app.include_router(attendance.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")


@app.get("/", tags=["System"])
async def root() -> dict:
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "online",
        "documentation": "/docs",
    }


@app.get("/health", tags=["System"])
async def health_check() -> dict:
    is_db_connected = False
    if DatabaseManager.client is not None:
        try:
            await DatabaseManager.client.admin.command("ping")
            is_db_connected = True
        except Exception:
            is_db_connected = False

    return {
        "status": "healthy" if is_db_connected else "degraded",
        "database_connected": is_db_connected,
        "version": settings.APP_VERSION,
    }

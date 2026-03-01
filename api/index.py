"""
Vercel Serverless API Entry Point
Converts FastAPI app to Vercel-compatible handler
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Import app components (lazy loading for serverless)
from app.config import settings
from app.routers import api_router, pages_router
from app.database import init_db, get_session_factory
from app.init_db import seed_categories, seed_sources


# Create a new FastAPI instance for Vercel
vercel_app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
)


@vercel_app.on_event("startup")
async def startup_event():
    """Initialize database tables and seed data on startup"""
    try:
        # Create tables
        await init_db()
        logger.info("Database tables initialized")
        
        # Seed default categories and sources
        session_factory = get_session_factory()
        async with session_factory() as session:
            try:
                await seed_categories(session)
                await seed_sources(session)
                logger.info("Database seeded with default sources")
            except Exception as e:
                logger.warning(f"Could not seed database: {e}")
    except Exception as e:
        logger.warning(f"Could not initialize database: {e}")


# Exception handler for better error visibility
@vercel_app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {type(exc).__name__}: {exc}")
    import traceback
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "type": type(exc).__name__}
    )


# Mount static files
try:
    vercel_app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")
    logger.info(f"Mounted static files from {settings.STATIC_DIR}")
except Exception as e:
    logger.warning(f"Could not mount static files: {e}")

# Include routers
try:
    vercel_app.include_router(pages_router)
    logger.info("Included pages router")
except Exception as e:
    logger.error(f"Error including pages router: {e}")

try:
    vercel_app.include_router(api_router)
    logger.info("Included API router")
except Exception as e:
    logger.error(f"Error including API router: {e}")


@vercel_app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


# Vercel handler - export the ASGI app
app = vercel_app

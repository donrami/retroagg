"""
Vercel Serverless API Entry Point
Converts FastAPI app to Vercel-compatible handler
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from starlette.responses import Response

# Import app components (lazy loading for serverless)
from app.config import settings
from app.routers import api_router, pages_router


# Create a new FastAPI instance for Vercel
vercel_app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
)

# Mount static files
try:
    vercel_app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")
except Exception:
    pass  # Static files may not be available in all environments

# Include routers
vercel_app.include_router(pages_router)
vercel_app.include_router(api_router)


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

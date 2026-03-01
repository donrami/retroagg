"""
Routers package
"""
from app.routers.api import router as api_router
from app.routers.pages import router as pages_router

__all__ = ["api_router", "pages_router"]

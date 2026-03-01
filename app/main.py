"""
RetroAgg - Main FastAPI Application
Vibe-coded news aggregator with late 90s brutalist aesthetics
"""
import sys
from pathlib import Path

# Add parent directory to path for absolute imports when running directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging

from app.config import settings
from app.database import init_db, close_db
from app.scheduler import start_scheduler, stop_scheduler
from app.routers import api_router, pages_router


logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Remove server identification
        response.headers["Server"] = "RetroAgg"
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting per IP"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = {}
        self.cleanup_interval = 60  # seconds
        self.last_cleanup = time.time()
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        
        # Periodic cleanup of old entries
        current_time = time.time()
        if current_time - self.last_cleanup > self.cleanup_interval:
            self.request_counts = {
                ip: times for ip, times in self.request_counts.items()
                if times and current_time - times[-1] < 60
            }
            self.last_cleanup = current_time
        
        # Check rate limit
        if client_ip in self.request_counts:
            # Remove requests older than 1 minute
            self.request_counts[client_ip] = [
                t for t in self.request_counts[client_ip]
                if current_time - t < 60
            ]
            
            if len(self.request_counts[client_ip]) >= self.requests_per_minute:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please try again later."}
                )
            
            self.request_counts[client_ip].append(current_time)
        else:
            self.request_counts[client_ip] = [current_time]
        
        response = await call_next(request)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized.")
    
    # Start background scheduler
    start_scheduler()
    logger.info("Background scheduler started.")
    
    yield
    
    # Shutdown - proper cleanup
    logger.info("Shutting down application...")
    stop_scheduler()
    await close_db()
    logger.info(f"{settings.APP_NAME} shutdown complete.")


# Create FastAPI app with security settings
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    # Disable automatic docs for production security
    docs_url=None if not settings.DEBUG else "/docs",
    redoc_url=None if not settings.DEBUG else "/redoc",
)

# Add security middleware (order matters - added first, executed last)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)

# Add CORS middleware with strict settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    max_age=600,
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(settings.STATIC_DIR)), name="static")

# Include routers
app.include_router(pages_router)
app.include_router(api_router)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # Production settings
        workers=4,  # Multiple workers for concurrent requests
        limit_concurrency=100,
        limit_max_requests=1000,
        timeout_keep_alive=30,
    )
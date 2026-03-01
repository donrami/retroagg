"""
RetroAgg Configuration Settings
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    """Application settings"""
    
    # App metadata
    APP_NAME: str = "RetroAgg"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "A vibe-coded news aggregator with late 90s brutalist aesthetics"
    
    # Debug mode (should be False in production)
    DEBUG: bool = False
    
    # Database - Override with external DB for Vercel (e.g., Neon, Supabase, Turso)
    # Format: postgresql+asyncpg://user:pass@host/dbname
    # For SQLite local dev: sqlite+aiosqlite:///data/retroagg.db
    DATABASE_URL: str = "sqlite+aiosqlite:///data/retroagg.db"
    
    # RSS Fetching
    FETCH_INTERVAL_MINUTES: int = 15
    REQUEST_TIMEOUT: int = 30
    MAX_RETRIES: int = 3
    
    # Deduplication
    DUPLICATE_THRESHOLD: float = 0.70  # 70% headline similarity
    
    # UI
    MAX_SUMMARY_LENGTH: int = 300
    
    # Rate limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Article content caching (for multi-user deployment)
    CONTENT_CACHE_TTL_HOURS: int = 24  # Cache extracted article content for 24 hours
    
    # Paths - use absolute paths that work in Vercel
    BASE_DIR: Path = Path(__file__).parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    TEMPLATES_DIR: Path = BASE_DIR / "app" / "templates"
    STATIC_DIR: Path = BASE_DIR / "app" / "static"
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Allow extra fields in env


# Global settings instance
settings = Settings()
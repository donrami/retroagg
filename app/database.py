"""
Database configuration and session management
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Lazy initialization to avoid import-time errors
_engine = None
_session_factory = None


def get_engine():
    """Lazy engine initialization"""
    global _engine
    if _engine is None:
        url = settings.DATABASE_URL.lower()
        
        # Check for libsql URL - warn user to use PostgreSQL instead
        if "libsql" in url:
            logger.warning(
                "libsql URL detected. For Vercel, please use PostgreSQL instead. "
                "Set DATABASE_URL to a PostgreSQL connection string (e.g., from Neon)."
            )
            # Fall back to in-memory SQLite (won't persist but won't crash)
            _engine = create_async_engine(
                "sqlite+aiosqlite:///:memory:",
                echo=False,
                poolclass=NullPool,
            )
        elif "sqlite" in url or "aiosqlite" in url:
            # Use NullPool for SQLite-like databases in serverless
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=False,
                poolclass=NullPool,
            )
        else:
            # Use connection pooling for PostgreSQL in production
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=False,
                poolclass=AsyncAdaptedQueuePool,
                pool_size=10,
                max_overflow=20,
                pool_timeout=30,
                pool_recycle=1800,
                pool_pre_ping=True,
            )
        
        logger.info(f"Database engine initialized: {url[:30]}...")
    
    return _engine


# Session factory with proper configuration
def get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


# Base class for models
Base = declarative_base()


# Backwards compatibility aliases
AsyncSessionLocal = get_session_factory


# For backwards compatibility - use lazy getter
class _EngineProxy:
    def __call__(self):
        return get_engine()
    
    def __getattr__(self, name):
        return getattr(get_engine(), name)


engine = _EngineProxy()


async def get_db():
    """Dependency for getting database sessions with proper cleanup"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Properly close database connections on shutdown"""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
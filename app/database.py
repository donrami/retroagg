"""
Database configuration and session management
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.pool import AsyncAdaptedQueuePool

from app.config import settings


# Create async engine with connection pooling for multi-user support
# Using AsyncAdaptedQueuePool for better concurrent access
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    # Use connection pooling for better multi-user performance
    # NullPool is fine for SQLite single connection, but queue pool for production
    poolclass=AsyncAdaptedQueuePool,
    pool_size=10,          # Base number of connections
    max_overflow=20,       # Additional connections when pool is exhausted
    pool_timeout=30,       # Wait time for available connection
    pool_recycle=1800,     # Recycle connections after 30 minutes
    pool_pre_ping=True,    # Verify connections before use
)

# Session factory with proper configuration
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)

# Base class for models
Base = declarative_base()


async def get_db():
    """Dependency for getting database sessions with proper cleanup"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Properly close database connections on shutdown"""
    await engine.dispose()
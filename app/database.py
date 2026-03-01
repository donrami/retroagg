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
        elif "postgresql" in url or "postgres" in url:
            # Use asyncpg for PostgreSQL - need to add asyncpg driver to URL
            db_url = settings.DATABASE_URL
            # Convert postgresql:// to postgresql+asyncpg://
            if "postgresql://" in db_url:
                db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif "postgres://" in db_url:
                db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
            
            # Remove unsupported query params from URL and pass as connect_args
            import urllib.parse
            parsed = urllib.parse.urlparse(db_url)
            query_params = urllib.parse.parse_qsl(parsed.query)
            
            sslmode = "require"
            # Extract and remove unsupported params
            new_params = []
            for key, value in query_params:
                if key == "sslmode":
                    sslmode = value
                elif key == "channel_binding":
                    # Skip this param - not supported by asyncpg
                    continue
                else:
                    new_params.append((key, value))
            
            # Rebuild URL without unsupported params
            db_url = urllib.parse.urlunparse((
                parsed.scheme, parsed.netloc, parsed.path, parsed.params,
                urllib.parse.urlencode(new_params), parsed.fragment
            ))
            
            _engine = create_async_engine(
                db_url,
                echo=False,
                pool_pre_ping=True,
                connect_args={"ssl": sslmode},
            )
        else:
            # Default - use NullPool
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=False,
                poolclass=NullPool,
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
from src.shared.config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

DATABASE_URL = settings.DATABASE_URL

# Async URL for asyncpg (postgresql+asyncpg://...)
ASYNC_DATABASE_URL = (
    DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    .replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
)
if not ASYNC_DATABASE_URL.startswith("postgresql+asyncpg"):
    ASYNC_DATABASE_URL = "postgresql+asyncpg://" + DATABASE_URL.split("://", 1)[-1]

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=settings.DB_POOL_SIZE > 0,
    pool_size=settings.DB_POOL_SIZE if settings.DB_POOL_SIZE > 0 else None,
    max_overflow=settings.DB_MAX_OVERFLOW if settings.DB_POOL_SIZE > 0 else None,
    pool_recycle=1800, # Reduced to 30 mins to flush stale connections
    pool_timeout=15,   # Faster failure when pool is exhausted
    connect_args={"connect_timeout": 10},
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # Keep committed objects usable in same request (avoids invalid session on next insert)
)

# Async engine and session (connection pooling via create_async_engine)
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    pool_pre_ping=settings.DB_POOL_SIZE > 0,
    pool_size=settings.DB_POOL_SIZE if settings.DB_POOL_SIZE > 0 else None,
    max_overflow=settings.DB_MAX_OVERFLOW if settings.DB_POOL_SIZE > 0 else None,
    pool_recycle=1800,
    pool_timeout=15,
    connect_args={"command_timeout": 10},
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db():
    """Yield AsyncSession for async route handlers. One session per request, closed after use."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


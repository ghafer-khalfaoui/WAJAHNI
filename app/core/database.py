from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

# Instantiate the asynchronous database engine with enterprise connection pooling parameters
async_engine = create_async_engine(
    settings.DATABASE_ASYNC_URL,
    echo=False,              # Set to True only for low-level SQL query auditing in local development
    pool_size=20,            # High-performance baseline of persistent concurrent connections
    max_overflow=10,         # Safe overflow connection allowance during intense burst traffic periods
    pool_recycle=3600,       # Recycle connections every hour to mitigate silent stale dropouts
    pool_pre_ping=True,       # Pre-ping database liveness to prevent runtime broken pipe anomalies
)

# Construct the stateful session factory for driving ACID transactions
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Critical flag: prevents SQLAlchemy from wiping object memory post-commit
    autocommit=False,
    autoflush=False,
)

# Declarative ORM base mapping engine inherited by all multi-tenant domain models
Base = declarative_base()

# Context-aware Dependency Injection provider for FastAPI endpoint routes
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Spawns an isolated transactional context block for an individual incoming API request.
    Leverages async context management to guarantee absolute database resource teardown.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
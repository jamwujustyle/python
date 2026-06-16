from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from app.core.config import settings

connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    # SQLite needs check_same_thread=False for async multithreading
    connect_args["check_same_thread"] = False
elif settings.DATABASE_URL.startswith("postgresql"):
    # asyncpg requires ssl=False passed via connect_args, not as a URL query param
    connect_args["ssl"] = False

engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    echo=False,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database sessions."""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
            
            
async def init_db() -> None:
    """Utility to initialize tables. Used mainly in development and tests."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

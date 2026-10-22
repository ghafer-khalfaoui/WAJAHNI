"""Helpers for opt-in database tests. Everything happens inside a temporary schema that is
created and dropped here, so real tables are never touched."""
import asyncio
import uuid
from contextlib import contextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def _tables():
    import app.models  # noqa: F401  (registers every model)
    from app.models.academic import AcademicEvent, Course, CoursePrerequisite, Instructor
    from app.models.university import University

    return [
        University.__table__, Course.__table__, CoursePrerequisite.__table__, Instructor.__table__,
        AcademicEvent.__table__,
    ]


def scoped_engine(url: str, schema: str):
    return create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})


@contextmanager
def scratch_schema(url: str):
    schema = f"wajahni_test_{uuid.uuid4().hex[:10]}"

    async def create():
        admin = create_async_engine(url)
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        await admin.dispose()
        engine = scoped_engine(url, schema)
        from app.core.database import Base

        async with engine.begin() as conn:
            await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=_tables()))
        await engine.dispose()

    async def drop():
        admin = create_async_engine(url)
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()

    asyncio.run(create())
    try:
        yield schema
    finally:
        asyncio.run(drop())


def run_in_schema(url: str, schema: str, work):
    """Run `async def work(db)` against the scratch schema and return its result."""

    async def go():
        engine = scoped_engine(url, schema)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as db:
                return await work(db)
        finally:
            await engine.dispose()

    return asyncio.run(go())


def db_override(url: str, schema: str):
    """A FastAPI `get_db` replacement that opens its connection inside the app's own event loop."""

    async def _get_db():
        engine = scoped_engine(url, schema)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as db:
                yield db
        finally:
            await engine.dispose()

    return _get_db

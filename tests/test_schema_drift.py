"""Compare the ORM models with a REAL database (read-only).

Skipped unless WAJAHNI_TEST_DB_URL is set, e.g. in PowerShell:
  $env:WAJAHNI_TEST_DB_URL = "postgresql+asyncpg://wajahni:PASSWORD@localhost:5432/wajahni"
  .\\.venv\\Scripts\\python.exe -m pytest tests/test_schema_drift.py -q
Run `alembic upgrade head` first. Nothing is written to the database.
"""
import asyncio
import os

import pytest

URL = os.environ.get("WAJAHNI_TEST_DB_URL")
pytestmark = pytest.mark.skipif(not URL, reason="set WAJAHNI_TEST_DB_URL to run against a real database")


def _load_database_columns():
    from sqlalchemy import inspect
    from sqlalchemy.ext.asyncio import create_async_engine

    async def run():
        engine = create_async_engine(URL)
        try:
            async with engine.connect() as conn:
                def read(sync_conn):
                    insp = inspect(sync_conn)
                    return {
                        t: {c["name"]: c["nullable"] for c in insp.get_columns(t)}
                        for t in insp.get_table_names()
                    }
                return await conn.run_sync(read)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_models_match_database():
    import app.models.document  # noqa: F401
    import app.models.student  # noqa: F401
    import app.models.university  # noqa: F401
    from app.core.database import Base

    database = _load_database_columns()
    problems = []
    for name, table in Base.metadata.tables.items():
        if name not in database:
            problems.append(f"{name}: table is missing in the database")
            continue
        model = {c.name: c.nullable for c in table.columns}
        db = database[name]
        for col in sorted(set(model) - set(db)):
            problems.append(f"{name}.{col}: in model, missing in database")
        for col in sorted(set(db) - set(model)):
            problems.append(f"{name}.{col}: in database, missing in model")
        for col in sorted(set(model) & set(db)):
            if model[col] != db[col]:
                problems.append(f"{name}.{col}: nullable differs (model={model[col]}, db={db[col]})")
    assert not problems, "\n" + "\n".join(problems)

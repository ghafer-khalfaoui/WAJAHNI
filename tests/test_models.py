from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.dialects import postgresql

import app.models.document  # noqa: F401  (registers tables)
import app.models.student  # noqa: F401
import app.models.university  # noqa: F401
from app.core.database import Base
from app.services.vector_store import VectorStoreService

ROOT = Path(__file__).resolve().parents[1]


def test_expected_tables_are_registered():
    import app.models.academic  # noqa: F401

    assert set(Base.metadata.tables) == {
        "universities", "students", "documents", "documentchunks", "admin_users",
        "courses", "course_prerequisites", "instructors", "academic_events",
    }


def test_migrations_have_a_single_head():
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert heads == ["f3a9c1d7e054"]


def test_search_query_is_restricted_to_one_university():
    sql = str(
        VectorStoreService.build_search_query(7, [0.0] * 768, limit=3).compile(
            dialect=postgresql.dialect()
        )
    )
    assert "documentchunks.university_id =" in sql
    assert "LIMIT" in sql


def test_search_limit_is_bounded():
    q = VectorStoreService.build_search_query(1, [0.0] * 768, limit=10_000)
    assert q._limit_clause.value == 20


def test_importing_one_model_is_enough_to_configure_all_mappers():
    """Regression: scripts that import only `University` used to crash."""
    import subprocess
    import sys

    code = (
        "import app.models.university; "
        "from sqlalchemy.orm import configure_mappers; configure_mappers(); print('ok')"
    )
    done = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0 and "ok" in done.stdout, done.stderr[-500:]


def test_chunks_and_admins_require_a_university():
    assert Base.metadata.tables["documentchunks"].c.university_id.nullable is False
    assert Base.metadata.tables["admin_users"].c.university_id.nullable is False

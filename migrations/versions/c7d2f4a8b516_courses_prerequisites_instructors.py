"""Add courses, course_prerequisites, instructors

Revision ID: c7d2f4a8b516
Revises: a3c5e7f91b24
Create Date: 2026-10-21

Structured academic data for exact lookups (course info, prerequisites, staff
directory). Every row is tenant-scoped and carries `source` and `verified`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7d2f4a8b516"
down_revision: Union[str, None] = "a3c5e7f91b24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base_columns() -> list:
    return [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    uni_fk = lambda: sa.ForeignKeyConstraint(["university_id"], ["universities.id"], ondelete="CASCADE")  # noqa: E731

    op.create_table(
        "courses",
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("credit_hours", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_base_columns(),
        uni_fk(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("university_id", "code", name="uq_courses_university_code"),
    )
    op.create_index(op.f("ix_courses_id"), "courses", ["id"], unique=False)
    op.create_index(op.f("ix_courses_university_id"), "courses", ["university_id"], unique=False)

    op.create_table(
        "course_prerequisites",
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("prerequisite_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_base_columns(),
        uni_fk(),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prerequisite_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("course_id", "prerequisite_id", name="uq_course_prerequisite_pair"),
        sa.CheckConstraint("course_id <> prerequisite_id", name="ck_course_not_own_prerequisite"),
    )
    op.create_index(op.f("ix_course_prerequisites_id"), "course_prerequisites", ["id"], unique=False)
    op.create_index(op.f("ix_course_prerequisites_university_id"), "course_prerequisites", ["university_id"], unique=False)
    op.create_index(op.f("ix_course_prerequisites_course_id"), "course_prerequisites", ["course_id"], unique=False)
    op.create_index(op.f("ix_course_prerequisites_prerequisite_id"), "course_prerequisites", ["prerequisite_id"], unique=False)

    op.create_table(
        "instructors",
        sa.Column("university_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=True),
        sa.Column("office_location", sa.String(length=50), nullable=True),
        sa.Column("phone", sa.String(length=60), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        *_base_columns(),
        uni_fk(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("university_id", "email", name="uq_instructors_university_email"),
    )
    op.create_index(op.f("ix_instructors_id"), "instructors", ["id"], unique=False)
    op.create_index(op.f("ix_instructors_university_id"), "instructors", ["university_id"], unique=False)
    op.create_index(op.f("ix_instructors_name"), "instructors", ["name"], unique=False)


def downgrade() -> None:
    op.drop_table("instructors")
    op.drop_table("course_prerequisites")
    op.drop_table("courses")
